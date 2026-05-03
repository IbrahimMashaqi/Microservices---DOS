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

It holds no data of its own and uses environment variables (`CATALOG_URL`, `ORDER_URL`) to locate the back-end services, making it easy to reconfigure for different deployments.

### Catalog Server (`catalog/app.py`)
Maintains a SQLite database (`catalog.db`) with a single `books` table containing:

| Column | Type | Description |
|--------|------|-------------|
| id | INTEGER | Item number (1–4) |
| title | TEXT | Book title |
| topic | TEXT | Subject category |
| quantity | INTEGER | Copies in stock |
| price | REAL | Price in USD |

The database is seeded on first launch with the four books. The server exposes:
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

Both the Catalog and Order servers use **SQLite**, a lightweight, file-based relational database. SQLite requires no server process and stores all data in a single `.db` file. Docker named volumes (`catalog_data`, `order_data`) ensure the database files survive container restarts.

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

# 2. Build and start all three containers
docker-compose up --build

# 3. In a separate terminal, run the test client
cd client/
pip install requests
python client.py
```

All three services will be reachable at:
- Front-End: `http://localhost:5000`
- Catalog:   `http://localhost:5001`
- Order:     `http://localhost:5002`

### Example curl commands

```bash
# Search
curl http://localhost:5000/search/distributed%20systems

# Info
curl http://localhost:5000/info/2

# Purchase
curl -X POST http://localhost:5000/purchase/2
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

- **Caching in the front-end**: Cache recent `info` and `search` responses to reduce load on the catalog.
- **HTTPS/TLS**: Terminate TLS at the front-end for secure client connections.
- **Authentication & Authorization**: Add API keys or JWT tokens to protect purchase and update endpoints.
- **Atomic purchase in catalog**: Move the stock-check-and-decrement into a single SQL transaction in the catalog server to eliminate the race condition.
- **Health checks**: Add `GET /health` endpoints to each service and configure Docker healthchecks.
- **Rate limiting**: Prevent abuse by limiting requests per client IP.
- **Restock API**: Expose a `PUT /update/<id>` endpoint from the front-end to allow restocking without direct catalog access.
