# Bazar.com — Design Document

## 1. Overview

Bazar.com is a minimal, multi-tier online book store implemented as three independent Flask microservices. The system follows a classic two-tier web architecture: a stateless **front-end** tier that acts as an API gateway for clients, and a **back-end** tier consisting of a catalog service and an order service. Each service runs in its own Docker container and communicates with others using HTTP REST calls.

---

## 2. Architecture

```
Client (browser / curl / client.py)
           |
           | HTTP REST  (port 5000)
           v
  ┌─────────────────────┐
  │   Front-End Server  │   (stateless proxy)
  └────────┬────────────┘
           |                       |
     GET /search, /info      POST /purchase
           |                       |
           v                       v
  ┌─────────────────┐     ┌─────────────────┐
  │  Catalog Server │<────│  Order Server   │
  │   (port 5001)   │     │   (port 5002)   │
  │   catalog.db    │     │   orders.db     │
  └─────────────────┘     └─────────────────┘
```

### Components

| Component | Port | Responsibility |
|-----------|------|----------------|
| Front-End Server | 5000 | Receives client requests; routes to catalog/order |
| Catalog Server | 5001 | Stores and serves book data; handles search, info, update |
| Order Server | 5002 | Processes purchases; queries and updates catalog |

---

## 3. How It Works

### Front-End Server (`frontend/app.py`)
The front-end is a **stateless proxy**. It exposes three endpoints to clients:

- `GET /search/<topic>` — forwarded to Catalog `/search/<topic>`
- `GET /info/<item_id>` — forwarded to Catalog `/info/<item_id>`
- `POST /purchase/<item_id>` — forwarded to Order `/purchase/<item_id>`

It holds no data of its own and uses environment variables (`CATALOG_REPLICAS`, `ORDER_REPLICAS`) to locate the back-end services, making it easy to reconfigure for different deployments.

### Catalog Server (`catalog/app.py`)
Maintains a SQLite database (`catalog.db`) with a single `books` table containing:

| Column | Type | Description |
|--------|------|-------------|
| id | INTEGER | Item number (1–7) |
| title | TEXT | Book title |
| topic | TEXT | Subject category |
| quantity | INTEGER | Copies in stock |
| price | REAL | Price in USD |

The database is seeded on first launch with all seven books (four original + three added in Lab 2). The server exposes:
- `GET /search/<topic>` — returns all books matching the topic
- `GET /info/<id>` — returns title, quantity, and price for a book
- `PUT /update/<id>` — adjusts quantity (delta) and/or price (absolute)

### Order Server (`order/app.py`)
Maintains a SQLite database (`orders.db`) logging all completed purchases.

`POST /purchase/<id>` does the following atomically:
1. `GET /info/<id>` from Catalog to check stock
2. If `quantity > 0`, `PUT /update/<id>` with `{"quantity": -1}` to decrement stock
3. Insert a row into the `orders` table with book_id, book_title, and UTC timestamp
4. Return a success message or error if out of stock / not found

---

## 4. REST API Reference

### Catalog Server (`:5001`)

```
GET  /search/<topic>      Search books by topic
GET  /info/<id>           Get book details by ID
PUT  /update/<id>         Update stock (delta) or price (absolute)
```

### Order Server (`:5002`)

```
POST /purchase/<id>       Purchase a book by ID
```

### Front-End Server (`:5000`) — Client-facing

```
GET  /search/<topic>      → proxied to Catalog
GET  /info/<id>           → proxied to Catalog
POST /purchase/<id>       → proxied to Order
```

---

## 5. Persistence

Both the Catalog and Order servers use **SQLite**, a lightweight, file-based relational database. SQLite requires no server process and stores all data in a single `.db` file. Docker named volumes (`catalog1_data`, `catalog2_data`, `order1_data`, `order2_data`) ensure each replica's database file survives container restarts independently.

All write operations are protected by a Python `threading.Lock()` to prevent race conditions when Flask handles multiple concurrent requests.

---

## 6. Concurrency

Flask is run with `threaded=True`, allowing it to handle multiple simultaneous requests using one thread per request. SQLite access is serialised using a per-process `threading.Lock`, which is sufficient for this workload. For higher throughput, the lock could be replaced with connection pooling (e.g., SQLAlchemy) or a server-based database.

---

## 7. How to Run

### Prerequisites
- Docker Desktop installed and running

### Steps

```bash
# 1. Clone/download the repository
cd DOS/

# 2. Build and start all five containers
docker-compose up --build

# 3. In a separate terminal, run the full test suite (Lab 1 + Lab 2)
cd client/
pip install requests
python client.py
```

All services will be reachable at:

| Service | Host Port | Description |
|---------|-----------|-------------|
| Front-End | 5000 | Client-facing gateway (all client requests go here) |
| Catalog replica 1 | 5001 | Primary catalog server |
| Catalog replica 2 | 5011 | Secondary catalog server |
| Order replica 1 | 5002 | Primary order server |
| Order replica 2 | 5012 | Secondary order server |

### Example curl commands

```bash
# Search (load-balanced across catalog replicas)
curl http://localhost:5000/search/distributed%20systems

# Info — 1st call is a cache miss, 2nd is a cache hit
curl http://localhost:5000/info/2
curl http://localhost:5000/info/2

# Purchase (triggers cache invalidation + replica sync)
curl -X POST http://localhost:5000/purchase/2

# Verify stock decreased (cache miss, returns fresh value)
curl http://localhost:5000/info/2
```

---

## 8. Design Tradeoffs

| Decision | Choice Made | Alternative | Reason |
|----------|-------------|-------------|--------|
| Language | Python + Flask | Java/Spark, PHP/Lumen | Fastest iteration; Flask is the lightest option |
| Persistence | SQLite | CSV files | Better concurrency safety; supports transactions |
| Inter-service comms | HTTP REST (requests lib) | gRPC, message queues | Matches lab requirement; simple and debuggable |
| Concurrency | threading.Lock + threaded Flask | asyncio / gunicorn | Simplest correct solution for low concurrency |
| Containerisation | Docker Compose | Manual Docker | Single command to run all three services |

---

## 9. Known Limitations

- **No authentication**: Any client can purchase, update, or query any book with no authorization.
- **SQLite locking**: Under very high concurrent write load, SQLite's file-level lock can become a bottleneck. A production system would use PostgreSQL or MySQL.
- **No retry logic**: If the catalog is unreachable during a purchase, the order fails immediately without retrying.
- **Stock race condition**: While the threading lock protects within a single process, the check-and-decrement of stock in the order server is not a true atomic transaction across HTTP calls (two simultaneous purchases could theoretically both see `quantity=1` and both succeed). This could be solved by moving the decrement logic into the catalog server as a single atomic SQL operation.

---

## 10. Possible Improvements

- **HTTPS/TLS**: Terminate TLS at the front-end for secure client connections.
- **Authentication & Authorization**: Add API keys or JWT tokens to protect purchase and update endpoints.
- **Atomic purchase in catalog**: Move the stock-check-and-decrement into a single SQL transaction in the catalog server to eliminate the race condition.
- **Health checks**: Add `GET /health` endpoints to each service and configure Docker healthchecks.
- **Rate limiting**: Prevent abuse by limiting requests per client IP.
- **Restock API**: Expose a `PUT /update/<id>` endpoint from the front-end to allow restocking without direct catalog access.

---

## 11. Lab 2: Replication, Caching and Consistency

### 11.1 New Books

Three new books were added to the catalog (IDs 5–7):

| ID | Title | Topic |
|----|-------|-------|
| 5 | How to finish Project 3 on time | distributed systems |
| 6 | Why theory classes are so hard | undergraduate school |
| 7 | Spring in the Pioneer Valley | undergraduate school |

These are seeded in `catalog/app.py` alongside the original four.

---

### 11.2 Architecture Overview (Lab 2)

```
Client (browser / curl / client.py)
           |
           | HTTP REST  (port 5000)
           v
  ┌──────────────────────────────────┐
  │      Front-End Server            │
  │  ┌─────────────────────────┐     │
  │  │  LRU Cache (in-memory)  │     │
  │  │  item_id -> {info data} │     │
  │  └─────────────────────────┘     │
  │  Round-Robin Load Balancer        │
  └────────┬──────────────┬──────────┘
           |              |
     catalog replicas   order replicas
           |              |
  ┌────────┴────────┐  ┌──┴──────────────┐
  │   catalog1:5001 │  │  order1:5002     │
  │   catalog2:5011 │  │  order2:5012     │
  └────────┬────────┘  └──┬──────────────┘
           │ sync writes   │ sync orders
           └──────┬────────┘
                  │
         (peer-to-peer REST calls)
```

---

### 11.3 In-Memory Cache

The front-end server maintains an `OrderedDict`-based LRU cache keyed by `item_id`. The cache stores `{title, quantity, price}` results from `/info` requests.

- **Read path**: `GET /info/<id>` checks the cache first. On a hit, the result is returned immediately without hitting any catalog replica. On a miss, a catalog replica is queried via round-robin and the result is inserted into the cache.
- **Write path (search, purchase)**: Search results are not cached because they depend on mutable catalog state and are queried less repetitively. Purchase requests bypass the cache entirely and go directly to the order server.
- **Capacity**: The cache holds at most 100 entries. When full, the least-recently-used entry is evicted (`OrderedDict.popitem(last=False)`).
- **Thread safety**: All cache operations are protected by a `threading.Lock` to prevent races between concurrent Flask threads.

---

### 11.4 Cache Consistency (Server-Push Invalidation)

Strong consistency is maintained using a **server-push invalidation** protocol:

1. When the catalog server receives a `PUT /update/<id>` request (triggered by a purchase or restock), it sends a `POST /invalidate/<id>` to the front-end **before writing** to its SQLite database.
2. The front-end removes the stale entry from the cache.
3. The catalog then performs the write and syncs to its peer replica.
4. The next `/info/<id>` request will be a cache miss and fetch the up-to-date value.

This guarantees that no client ever reads stale stock or price data from the cache after a write has been committed.

---

### 11.5 Replication

**Catalog replication**

Two catalog replicas (`catalog1`, `catalog2`) run the same `catalog/app.py` image. Each is seeded independently on first launch with the same seven books.

When a write arrives at a replica:
1. The replica invalidates the front-end cache (see §11.4).
2. It writes to its own SQLite database.
3. It forwards the same update to the peer replica with the internal flag `_sync=True`, which causes the peer to apply the write without triggering another invalidation or another sync (preventing infinite loops).

**Order replication**

Two order replicas (`order1`, `order2`) share the same logic. After a successful purchase is logged locally, the replica calls `POST /sync_order` on its peer, which inserts an identical record into the peer's `orders.db`. This keeps both order logs in sync.

---

### 11.6 Load Balancing

The front-end uses a **per-request round-robin** policy for both service tiers:

- `search` and `info` requests alternate between `catalog1` and `catalog2`.
- `purchase` requests alternate between `order1` and `order2`.

The replica lists are injected via the `CATALOG_REPLICAS` and `ORDER_REPLICAS` environment variables (comma-separated URLs), making it trivial to add more replicas without code changes. The order server also applies round-robin when it calls the catalog internally.

---

### 11.7 Design Tradeoffs (Lab 2)

| Decision | Choice Made | Alternative | Reason |
|----------|-------------|-------------|--------|
| Cache granularity | Per item-id (info only) | Per topic (search too) | Info results change on every purchase; search results change less often and are larger |
| Invalidation strategy | Server-push before write | Client-pull (TTL expiry) | Stronger consistency guarantee; no stale reads allowed |
| Replica sync | Best-effort async POST | Synchronous 2-phase commit | Simpler; acceptable for lab-scale workload; noted as limitation |
| Load balancing | Round-robin | Least-loaded, consistent hash | No health data available at this scale; round-robin is fair and stateless |
| Cache integration | Embedded in front-end process | Separate cache microservice | Avoids an extra network hop; simpler deployment |

---

### 11.8 Known Limitations (Lab 2)

- **Best-effort replica sync**: If the peer catalog or order replica is down when a sync is attempted, the sync is silently dropped. The replicas will diverge until the peer restarts and catches up (a full reconciliation protocol is out of scope).
- **Circular dependency on startup**: `frontend` depends on all four backend services. If any backend container starts slowly, the front-end may fail its first requests. In production, a health-check retry loop would handle this.
- **No replica failure detection**: The round-robin load balancer does not detect or skip failed replicas. A circuit-breaker pattern would improve resilience.

---

### 11.9 How to Run (Lab 2)

```bash
# Build and start all five containers
docker-compose up --build

# In a separate terminal, run the full test suite (Lab 1 + Lab 2)
cd client/
pip install requests
python client.py
```

Services are reachable at:

| Service | Host port | Description |
|---------|-----------|-------------|
| Front-End | 5000 | Client-facing gateway |
| Catalog replica 1 | 5001 | Primary catalog |
| Catalog replica 2 | 5011 | Secondary catalog |
| Order replica 1 | 5002 | Primary order server |
| Order replica 2 | 5012 | Secondary order server |

Example curl commands:

```bash
# Search (load-balanced across catalog replicas)
curl http://localhost:5000/search/distributed%20systems

# Info — first call is a cache miss, second is a cache hit
curl http://localhost:5000/info/2
curl http://localhost:5000/info/2

# Purchase (triggers cache invalidation + replica sync)
curl -X POST http://localhost:5000/purchase/2

# Verify stock decreased (cache miss, fetches fresh data)
curl http://localhost:5000/info/2
```
