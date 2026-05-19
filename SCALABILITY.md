# Scalability Roadmap

Living document tracking scalability issues in this project and the phased plan
to address them. Keep it simple — one phase at a time.

---

## Issues identified

| # | Issue | Where |
|---|-------|-------|
| 1 | Both services run in one Python process via `threading`; uses Flask's dev server | `main.py` |
| 2 | Hardcoded payment URL (`http://localhost:5001/payment`) | `monolith.py:6` |
| 3 | Synchronous blocking call to payment, no timeout / retry | `monolith.py:21` |
| 4 | No persistence; order id hardcoded to `1` | `monolith.py:12-16` |
| 5 | No idempotency keys → retries can double-charge | `gateway.py` |
| 6 | Minimal validation, no authn/authz, no rate limiting | `gateway.py` |
| 7 | No `/healthz` endpoints, no graceful shutdown | all services |
| 8 | No load tests — we don't actually know how many users we can serve | `tests/` |

---

## Handling lots of users / many clients

The bottlenecks that show up first under heavy load, ordered by what bites
soonest in a project this size:

1. **Single Flask dev server process.** Flask's built-in server handles one
   request at a time per thread and is not meant for production. Fix: run
   under **gunicorn** with several workers (`-w 4`) — instant N× concurrency
   without changing the code.
2. **Blocking HTTP call to payment.** Every order ties up a gateway worker
   until payment responds. Fix: short timeout + a couple of retries so a slow
   payment doesn't snowball; later, scale payment to multiple replicas so
   gateway workers aren't queuing on one instance.
3. **Hardcoded `localhost` URL.** Stops you from running more than one payment
   instance. Fix: env var + Docker DNS — then `docker compose up --scale payment=3`
   gives you three payment workers and Docker round-robins between them.
4. **No persistence layer.** As soon as orders matter, the in-memory `id=1`
   collides under concurrency. Fix: Postgres with a connection pool
   (SQLAlchemy default pool is enough at this scale).
5. **No idempotency.** Under load, clients retry. Without an idempotency key,
   each retry creates a duplicate order / duplicate payment. Fix: require an
   `Idempotency-Key` header and store it with the order.
6. **No rate limiting / no auth.** A single misbehaving client can saturate
   you. Fix later with `flask-limiter` (Redis-backed so it works across
   replicas).
7. **We don't measure.** Without a load test we're guessing. Fix: a small
   **k6** or **locust** script hitting `/api/orders` with N concurrent users.

Rule of thumb for "lots of users" in this project:
- gunicorn workers ≈ `2 * CPU_cores + 1` per service.
- Scale the **stateless** services horizontally (gateway, payment) via
  `docker compose --scale`.
- Scale the **stateful** part (Postgres) vertically first; only add replicas
  when reads dominate.
- Always put a timeout on any outbound HTTP call. Without it, one slow
  dependency drags everything down.

---

## Phased plan

### Phase 1 — Containerize ✅ start here
**Goal:** each service in its own container, configurable, production WSGI.

- `Dockerfile` for `gateway` and `payment_service`.
- Replace `app.run()` with **gunicorn**.
- Move payment URL into env var (`PAYMENT_SERVICE_URL`).
- `docker-compose.yml` with both services on a shared network — gateway
  reaches payment as `http://payment:5001/payment`.
- `main.py` becomes obsolete (compose orchestrates).

Addresses: **#1, #2**

### Phase 2 — Resilience on the network call
**Goal:** payment slowness/outages don't take down the gateway.

- Add `timeout=` to the `requests.post` call.
- Add a small retry with backoff (one extra dependency: `tenacity`).
- Add `/healthz` endpoint to both services.

Addresses: **#3, #7**

### Phase 3 — Persistence + idempotency
**Goal:** orders survive restarts; retries don't double-charge.

- Add **Postgres** as a container in compose.
- **SQLAlchemy** for the `orders` table; DB-generated id.
- Accept `Idempotency-Key` header on `POST /api/orders`; if the same key
  arrives again, return the original response instead of creating a new order.

Addresses: **#4, #5**

### Phase 4 — *To be decided after Phase 3*
Likely candidates: load test (k6/locust), rate limiting, observability
(structured logs + Prometheus metrics), auth. We'll choose based on what
hurts most after measuring.

---

## Rules of thumb

- One phase at a time. Don't start the next until the previous is green.
- Don't add Kafka, Kubernetes, or microservice tooling before the bottleneck
  is real and measured.
- Every new dependency is a new failure mode — justify each one.
- Always add a timeout to outbound HTTP calls.
