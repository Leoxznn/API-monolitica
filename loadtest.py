"""
Simple concurrent load test for POST /api/orders.

Usage:
    # default: 100 requests, 50 concurrent workers, against localhost:5000
    python loadtest.py

    # 500 requests, 100 concurrent
    python loadtest.py --requests 500 --concurrency 100

    # against a different host
    python loadtest.py --url http://localhost:5000/api/orders

Tips for finding limits:
    1. Start the stack:        docker compose up --build
    2. Run a baseline:         python loadtest.py -n 100 -c 10
    3. Crank concurrency:      python loadtest.py -n 500 -c 100
    4. Scale payment workers:  docker compose up --scale payment=3
       and re-run the same load — compare p95 / errors.
"""

import argparse
import statistics
import time
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests


def one_request(url: str, idempotent: bool):
    headers = {"Content-Type": "application/json"}
    if idempotent:
        headers["Idempotency-Key"] = str(uuid.uuid4())

    payload = {"item": "book", "price": 10}

    start = time.perf_counter()
    try:
        r = requests.post(url, json=payload, headers=headers, timeout=10)
        elapsed = time.perf_counter() - start
        instance = None
        try:
            instance = r.json().get("payment_instance")
        except ValueError:
            pass
        return {"ok": r.ok, "status": r.status_code, "elapsed": elapsed, "error": None, "instance": instance}
    except requests.RequestException as exc:
        elapsed = time.perf_counter() - start
        return {"ok": False, "status": None, "elapsed": elapsed, "error": str(exc), "instance": None}


def percentile(values, p):
    if not values:
        return 0.0
    s = sorted(values)
    k = int(round((p / 100) * (len(s) - 1)))
    return s[k]


def run(url: str, total: int, concurrency: int, idempotent: bool):
    print(f"→ {total} requests, {concurrency} concurrent workers")
    print(f"→ target: {url}")
    print(f"→ idempotency keys: {'on' if idempotent else 'off'}")
    print()

    results = []
    started = time.perf_counter()

    with ThreadPoolExecutor(max_workers=concurrency) as pool:
        futures = [pool.submit(one_request, url, idempotent) for _ in range(total)]
        done = 0
        for fut in as_completed(futures):
            results.append(fut.result())
            done += 1
            if done % max(1, total // 10) == 0:
                print(f"  {done}/{total} done")

    wall = time.perf_counter() - started
    latencies = [r["elapsed"] for r in results]
    ok = sum(1 for r in results if r["ok"])
    failed = total - ok

    by_status = {}
    for r in results:
        key = r["status"] if r["status"] is not None else f"ERR ({r['error'][:40]})"
        by_status[key] = by_status.get(key, 0) + 1

    print()
    print("──── results ────")
    print(f"  total time:     {wall:.2f}s")
    print(f"  throughput:     {total / wall:.1f} req/s")
    print(f"  success:        {ok}/{total}")
    print(f"  failed:         {failed}/{total}")
    print(f"  status codes:   {by_status}")
    print()
    print("──── latency (ms) ────")
    print(f"  min:    {min(latencies) * 1000:.1f}")
    print(f"  mean:   {statistics.mean(latencies) * 1000:.1f}")
    print(f"  median: {statistics.median(latencies) * 1000:.1f}")
    print(f"  p95:    {percentile(latencies, 95) * 1000:.1f}")
    print(f"  p99:    {percentile(latencies, 99) * 1000:.1f}")
    print(f"  max:    {max(latencies) * 1000:.1f}")
    print()

    by_instance = {}
    for r in results:
        if r.get("instance"):
            by_instance[r["instance"]] = by_instance.get(r["instance"], 0) + 1
    if by_instance:
        print("──── distribuição por instância (load balancer) ────")
        for inst, count in sorted(by_instance.items()):
            print(f"  {inst}: {count}")
        print()

    print("──── what to look at ────")
    print(" - failed > 0 or non-200 statuses → workers/timeouts saturated")
    print(" - throughput plateau when raising -c → bottleneck reached")
    print(" - p95/p99 ≫ median → tail latency (slow downstream / GC / lock)")
    print(" - re-run with `docker compose up --scale payment=3` and compare")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--url", default="http://localhost:5000/api/orders")
    p.add_argument("-n", "--requests", type=int, default=100)
    p.add_argument("-c", "--concurrency", type=int, default=50)
    p.add_argument(
        "--no-idempotency",
        action="store_true",
        help="Disable Idempotency-Key header (each request creates a new order)",
    )
    args = p.parse_args()
    run(args.url, args.requests, args.concurrency, idempotent=not args.no_idempotency)


if __name__ == "__main__":
    main()
