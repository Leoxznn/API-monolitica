# Theoretical Introduction

This document collects the core scalability concepts that motivate the
architectural choices in this project. It is meant as a quick reference, not
a textbook.

---

## 1. What is scalability?

**Scalability** is the property of a system that lets it handle a growing
amount of work — more users, more requests, more data — by adding resources.
A scalable system gets *more* capacity when you give it *more* hardware (or
processes); a non-scalable one hits a ceiling no matter how much you throw at
it.

Two related but distinct ideas:

- **Performance** — how fast a single request is served.
- **Scalability** — how the system behaves as concurrent load grows.

A fast system is not necessarily scalable: a single thread can serve one
request quickly but collapse under 1,000 concurrent ones.

### 1.1 Vertical vs. horizontal scaling

| | **Vertical (scale up)** | **Horizontal (scale out)** |
|---|---|---|
| **What** | Give the existing machine more CPU / RAM / disk | Run more machines (or containers) in parallel |
| **Pros** | Simple — no code changes; no distributed-system problems | Near-linear capacity growth; tolerates node failure |
| **Cons** | Hard cap (biggest machine you can buy); single point of failure; expensive at the top end | Requires stateless services, load balancing, distributed coordination |
| **Good for** | Databases, stateful services | Stateless web/API tiers |

Rule of thumb: scale **vertically first** until it gets expensive or risky,
then scale **horizontally**. Most systems end up doing both — vertical for
the database, horizontal for the application servers.

**References:**
- Martin Kleppmann, *Designing Data-Intensive Applications* (2017), Ch. 1.
- AWS — "Scaling vertically vs. horizontally": https://docs.aws.amazon.com/wellarchitected/latest/reliability-pillar/rel_adapt_to_changes_scale_up.html

---

## 2. Load balancing

A **load balancer** is a component that sits in front of N replicas of a
service and distributes incoming requests across them. Without it,
horizontal scaling is impossible — clients would have to know about every
replica.

Common strategies:
- **Round-robin** — request *i* goes to replica *i mod N*. Simple, fair when
  replicas are equally powerful.
- **Least connections** — pick the replica with fewest in-flight requests.
  Better when request durations vary.
- **Hash-based / consistent hashing** — route by a key (e.g. user id) so the
  same user lands on the same replica. Useful for caches.
- **Weighted** — give beefier replicas more traffic.

Load balancers also commonly provide:
- **Health checks** — stop sending traffic to a replica whose `/healthz`
  fails.
- **TLS termination** — decrypt HTTPS once, talk plain HTTP to backends.
- **Rate limiting** — drop or queue excess requests at the edge.

Layer 4 (TCP) load balancers route by IP/port; Layer 7 (HTTP) load
balancers can route by URL/headers. Examples: nginx, HAProxy, Traefik, AWS
ALB/NLB, the Kubernetes `Service` abstraction. Docker Compose itself
round-robins across replicas of a service via DNS.

**References:**
- NGINX — "What Is Load Balancing?": https://www.nginx.com/resources/glossary/load-balancing/
- Google SRE Book, Ch. 19 "Load Balancing at the Frontend": https://sre.google/sre-book/load-balancing-frontend/

---

## 3. Service replication

**Replication** means running multiple identical instances of a service.
The motivations are independent:

- **Throughput** — N replicas serve roughly N× the requests of one.
- **Availability** — if one replica crashes, the others keep serving.
- **Latency / locality** — replicas in different regions reduce round-trip
  time for nearby users.

Replication is straightforward for **stateless** services and gets much
harder for **stateful** ones. Stateful replicas must agree on the data they
hold; this is where the famous trade-offs (consistency vs. availability —
the **CAP theorem**) appear:

- **Leader/follower (primary/replica)** — one node accepts writes; followers
  replicate asynchronously. Cheap reads, possible staleness.
- **Multi-leader / multi-master** — any node accepts writes; conflicts must
  be resolved.
- **Quorum-based** — writes/reads succeed if a majority agrees (Raft, Paxos).

In this project we replicate the **stateless** services (gateway, payment)
and keep a **single** Postgres instance.

**References:**
- Kleppmann, *DDIA*, Ch. 5 "Replication".
- Eric Brewer, "CAP twelve years later": https://www.infoq.com/articles/cap-twelve-years-later-how-the-rules-have-changed/

---

## 4. Stateless vs. stateful

A service is **stateless** if any of its replicas can serve any request
without needing local memory of past requests. All required state lives
elsewhere — typically a database, cache, or message broker.

A service is **stateful** if it keeps in-process information that the next
request depends on (in-memory session, local cache, file on local disk,
etc.).

| | **Stateless** | **Stateful** |
|---|---|---|
| Replication | Trivial — just spin up more | Hard — replicas must coordinate |
| Failure | Lose a replica, lose nothing | Lose a replica, possibly lose data |
| Load balancing | Any strategy works | Often need session affinity or sticky routing |
| Deployment | Rolling restarts safe | Need careful coordination |

**Practical rules:**
- Push state out of the application: store it in Postgres / Redis / S3.
- Don't keep session data in process memory — use a shared store with a TTL.
- Don't write to local disk if you expect to scale horizontally — files
  live on one replica only.

In this project, gateway and payment are stateless; Postgres is the only
stateful component, which is why scaling the app tier is `--scale payment=3`
while the database stays a single container (for now).

**References:**
- Heroku, "The Twelve-Factor App" — especially factor VI ("Processes"):
  https://12factor.net/processes
- Microsoft Azure — "Stateless and stateful patterns":
  https://learn.microsoft.com/en-us/azure/architecture/guide/architecture-styles/

---

## 5. Bottlenecks in distributed systems

A **bottleneck** is the slowest component in the request path — the one
that decides total throughput. Adding capacity anywhere else is wasted until
the bottleneck is fixed (Amdahl's Law).

Common bottlenecks, in roughly the order they bite a small service:

1. **Single-process / single-threaded servers.** Flask's dev server, Node
   without clustering, etc. Fix: WSGI/ASGI server with multiple workers.
2. **Synchronous downstream calls.** A slow dependency holds a worker
   hostage. Fix: timeouts, retries with backoff, circuit breakers,
   asynchronous messaging.
3. **Database connections.** Apps usually run out of DB connections long
   before the DB runs out of CPU. Fix: connection pooling (`pgbouncer`,
   SQLAlchemy pool).
4. **Locks and serial sections.** A row-level lock or a global mutex
   serializes work that *looked* parallel. Fix: shorter transactions,
   optimistic concurrency, sharding.
5. **Network and I/O.** Bandwidth, DNS lookups, TLS handshakes. Fix:
   keep-alive, batching, caching.
6. **Caches.** A cold or undersized cache pushes load to the origin.
   Fix: warmer caches, larger TTLs, request coalescing.
7. **Coordination overhead.** As the cluster grows, gossip / heartbeat /
   consensus traffic grows non-linearly. Fix: hierarchical topologies,
   careful quorum sizing.

**Tail latency** matters as much as median latency. With a request that
fans out to 100 backends, the *slowest* backend dominates: even if 99% of
calls finish in 10 ms, the 1% at 1,000 ms set the user-visible latency.
This is the "tail at scale" problem.

How to find your bottleneck:
- **Measure first** — a load test with realistic concurrency.
- **Watch saturation** — CPU%, memory, DB connections in use, queue depth.
- **Trace requests** — distributed tracing reveals which hop is slow.
- **Apply Little's Law** — `concurrent_requests = throughput × latency`.
  If you want 1,000 RPS at 100 ms latency you need to handle 100 in-flight
  requests at once.

**References:**
- Jeff Dean & Luiz Barroso, "The Tail at Scale" (CACM, 2013):
  https://research.google/pubs/the-tail-at-scale/
- Brendan Gregg, "USE Method": https://www.brendangregg.com/usemethod.html
- Kleppmann, *DDIA*, Ch. 8 "The Trouble with Distributed Systems".

---

## Summary

| Concept | One-line takeaway |
|---|---|
| Vertical vs. horizontal | Scale up the simple stuff; scale out the stateless tier |
| Load balancing | The thing that makes horizontal scaling possible |
| Replication | More replicas → more throughput and resilience, but harder for stateful services |
| Stateless / stateful | Push state out; keep services replaceable |
| Bottlenecks | The slowest hop sets your throughput — measure, don't guess |
