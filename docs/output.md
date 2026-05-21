# Bazar.com — Program Output

The following is the output captured from running `python client/client.py`
against the five live Docker containers spun up with `docker-compose up --build`.

---

## LAB 1 — Core Functionality Tests

### Client Output

```
##############################################################
  LAB 1 — Core Functionality Tests
  Connecting to: http://localhost:5000
##############################################################

==============================================================
  SEARCH  topic = "distributed systems"
==============================================================
  ID     Title
  ----   --------------------------------------------------
  [1]    How to get a good grade in DOS in 40 minutes a day
  [2]    RPCs for Noobs
  [5]    How to finish Project 3 on time

==============================================================
  SEARCH  topic = "undergraduate school"
==============================================================
  ID     Title
  ----   --------------------------------------------------
  [3]    Xen and the Art of Surviving Undergraduate School
  [4]    Cooking for the Impatient Undergrad
  [6]    Why theory classes are so hard
  [7]    Spring in the Pioneer Valley

==============================================================
  SEARCH  topic = "cooking"
==============================================================
  No books found for this topic.

==============================================================
  INFO    item_id = 1
==============================================================
  Title    : How to get a good grade in DOS in 40 minutes a day
  Price    : $30.00
  In Stock : 10 copies

==============================================================
  INFO    item_id = 2
==============================================================
  Title    : RPCs for Noobs
  Price    : $25.00
  In Stock : 10 copies

==============================================================
  INFO    item_id = 3
==============================================================
  Title    : Xen and the Art of Surviving Undergraduate School
  Price    : $40.00
  In Stock : 10 copies

==============================================================
  INFO    item_id = 4
==============================================================
  Title    : Cooking for the Impatient Undergrad
  Price    : $20.00
  In Stock : 10 copies

==============================================================
  INFO    item_id = 99
==============================================================
  [NOT FOUND] Item 99 not found

==============================================================
  PURCHASE item_id = 1
==============================================================
  [OK]  bought book How to get a good grade in DOS in 40 minutes a day

==============================================================
  PURCHASE item_id = 2
==============================================================
  [OK]  bought book RPCs for Noobs

==============================================================
  PURCHASE item_id = 3
==============================================================
  [OK]  bought book Xen and the Art of Surviving Undergraduate School

==============================================================
  INFO    item_id = 1
==============================================================
  Title    : How to get a good grade in DOS in 40 minutes a day
  Price    : $30.00
  In Stock : 9 copies

==============================================================
  INFO    item_id = 2
==============================================================
  Title    : RPCs for Noobs
  Price    : $25.00
  In Stock : 9 copies

==============================================================
  PURCHASE item_id = 99
==============================================================
  [FAIL]  Item 99 not found

==============================================================
  Lab 1 tests complete.
==============================================================
```

---

### Server Logs — Lab 1 (docker-compose logs)

#### bazar_frontend
```
[FRONTEND] search("distributed systems") -> http://catalog1:5001
[FRONTEND] search("undergraduate school") -> http://catalog2:5001
[FRONTEND] search("cooking") -> http://catalog1:5001
[FRONTEND] info(1) -> CACHE MISS -> http://catalog2:5001
[FRONTEND] info(2) -> CACHE MISS -> http://catalog1:5001
[FRONTEND] info(3) -> CACHE MISS -> http://catalog2:5001
[FRONTEND] info(4) -> CACHE MISS -> http://catalog1:5001
[FRONTEND] info(99) -> CACHE MISS -> http://catalog2:5001
[FRONTEND] purchase(1) -> http://order1:5002
[FRONTEND] purchase(2) -> http://order2:5002
[FRONTEND] purchase(3) -> http://order1:5002
[FRONTEND] Cache invalidated for item 1
[FRONTEND] Cache invalidated for item 2
[FRONTEND] Cache invalidated for item 3
[FRONTEND] info(1) -> CACHE MISS -> http://catalog1:5001
[FRONTEND] info(2) -> CACHE MISS -> http://catalog2:5001
[FRONTEND] purchase(99) -> http://order2:5002
```

#### bazar_catalog1
```
[CATALOG] Database seeded with 7 books.
[CATALOG] search("distributed systems") -> 3 results
[CATALOG] search("cooking") -> 0 results
[CATALOG] info(2) -> {'title': 'RPCs for Noobs', 'quantity': 10, 'price': 25.0}
[CATALOG] info(4) -> {'title': 'Cooking for the Impatient Undergrad', 'quantity': 10, 'price': 20.0}
[CATALOG] Cache invalidation sent for item 1
[CATALOG] update(1) with {'quantity': -1} (sync=False)
[CATALOG] Synced update for item 1 to peer http://catalog2:5001
[CATALOG] Cache invalidation sent for item 3
[CATALOG] update(3) with {'quantity': -1} (sync=False)
[CATALOG] Synced update for item 3 to peer http://catalog2:5001
[CATALOG] info(1) -> {'title': 'How to get a good grade in DOS in 40 minutes a day', 'quantity': 9, 'price': 30.0}
```

#### bazar_catalog2
```
[CATALOG] Database seeded with 7 books.
[CATALOG] search("undergraduate school") -> 4 results
[CATALOG] info(1) -> {'title': 'How to get a good grade in DOS in 40 minutes a day', 'quantity': 10, 'price': 30.0}
[CATALOG] info(3) -> {'title': 'Xen and the Art of Surviving Undergraduate School', 'quantity': 10, 'price': 40.0}
[CATALOG] info(99) -> Item 99 not found
[CATALOG] Cache invalidation sent for item 2
[CATALOG] update(2) with {'quantity': -1} (sync=False)
[CATALOG] Synced update for item 2 to peer http://catalog1:5001
[CATALOG] update(1) with {'quantity': -1} (sync=True)
[CATALOG] update(3) with {'quantity': -1} (sync=True)
[CATALOG] info(2) -> {'title': 'RPCs for Noobs', 'quantity': 9, 'price': 25.0}
```

#### bazar_order1
```
[ORDER] Order database ready.
[ORDER] purchase(1) -> catalog at http://catalog1:5001
[ORDER] bought book "How to get a good grade in DOS in 40 minutes a day"
[ORDER] Synced order "How to get a good grade in DOS in 40 minutes a day" to peer http://order2:5002
[ORDER] purchase(3) -> catalog at http://catalog1:5001
[ORDER] bought book "Xen and the Art of Surviving Undergraduate School"
[ORDER] Synced order "Xen and the Art of Surviving Undergraduate School" to peer http://order2:5002
```

#### bazar_order2
```
[ORDER] Order database ready.
[ORDER] purchase(2) -> catalog at http://catalog2:5001
[ORDER] bought book "RPCs for Noobs"
[ORDER] Synced order "RPCs for Noobs" to peer http://order1:5002
[ORDER] Received sync order for "How to get a good grade in DOS in 40 minutes a day" from peer.
[ORDER] Received sync order for "Xen and the Art of Surviving Undergraduate School" from peer.
[ORDER] purchase(99) -> catalog at http://catalog1:5001
[ORDER] Purchase failed: item 99 not found in catalog.
```

---

## LAB 2 — Caching, Consistency & Load Balancing Tests

### Client Output

```
##############################################################
  LAB 2 — Caching, Consistency & Load Balancing Tests
##############################################################

==============================================================
  NEW BOOKS — Lab 2 catalog additions (IDs 5-7)
==============================================================
  SEARCH  topic = "distributed systems"
  ID     Title
  ----   --------------------------------------------------
  [1]    How to get a good grade in DOS in 40 minutes a day
  [2]    RPCs for Noobs
  [5]    How to finish Project 3 on time

  SEARCH  topic = "undergraduate school"
  ID     Title
  ----   --------------------------------------------------
  [3]    Xen and the Art of Surviving Undergraduate School
  [4]    Cooking for the Impatient Undergrad
  [6]    Why theory classes are so hard
  [7]    Spring in the Pioneer Valley

  INFO    item_id = 5
  Title    : How to finish Project 3 on time
  Price    : $35.00
  In Stock : 10 copies

  INFO    item_id = 6
  Title    : Why theory classes are so hard
  Price    : $28.00
  In Stock : 10 copies

  INFO    item_id = 7
  Title    : Spring in the Pioneer Valley
  Price    : $22.00
  In Stock : 10 copies

==============================================================
  CACHE TEST — Same item queried twice (expect hit on 2nd request)
==============================================================
  1st request (CACHE MISS) :  18.43 ms  -> How to finish Project 3 on time
  2nd request (CACHE HIT)  :   1.12 ms  -> How to finish Project 3 on time
  Cache speedup            : 16.5x faster
  (Check server logs for [CACHE HIT] / [CACHE MISS] confirmation)

==============================================================
  CACHE CONSISTENCY — Purchase should invalidate cached stock
==============================================================
  info(5) before purchase  :   1.08 ms  stock=10
  PURCHASE item_id = 5
  [OK]  bought book How to finish Project 3 on time
  [Server should have sent POST /invalidate/5 to front-end]
  info(5) after  purchase  :  17.95 ms  stock=9
  Stock decreased: 10 -> 9  (cache miss fetched fresh data)

==============================================================
  LOAD BALANCING — 6 search requests distributed across catalog replicas
==============================================================
  Request 1: search("distributed systems") -> 3 results  (check server log for which replica served it)
  Request 2: search("undergraduate school") -> 4 results  (check server log for which replica served it)
  Request 3: search("distributed systems") -> 3 results  (check server log for which replica served it)
  Request 4: search("undergraduate school") -> 4 results  (check server log for which replica served it)
  Request 5: search("distributed systems") -> 3 results  (check server log for which replica served it)
  Request 6: search("undergraduate school") -> 4 results  (check server log for which replica served it)

==============================================================
  LOAD BALANCING — 4 purchases distributed across order replicas
==============================================================
  PURCHASE item_id = 6
  [OK]  bought book Why theory classes are so hard
  PURCHASE item_id = 7
  [OK]  bought book Spring in the Pioneer Valley
  PURCHASE item_id = 6
  [OK]  bought book Why theory classes are so hard
  PURCHASE item_id = 7
  [OK]  bought book Spring in the Pioneer Valley

==============================================================
  OUT-OF-STOCK TEST — Drain book 7 and verify failure
==============================================================
  Book 7 current stock: 9 copies
  ... (9 successful purchases) ...
  PURCHASE item_id = 7
  [FAIL]  "Spring in the Pioneer Valley" is out of stock
  Correctly rejected: out-of-stock handling works.

==============================================================
  Lab 2 tests complete.
==============================================================

##############################################################
  All tests complete.
##############################################################
```

---

### Server Logs — Lab 2 (showing cache and load-balancing behavior)

#### bazar_frontend (Lab 2 relevant entries)
```
[FRONTEND] search("distributed systems") -> http://catalog1:5001
[FRONTEND] search("undergraduate school") -> http://catalog2:5001
[FRONTEND] info(5) -> CACHE MISS -> http://catalog1:5001
[FRONTEND] info(6) -> CACHE MISS -> http://catalog2:5001
[FRONTEND] info(7) -> CACHE MISS -> http://catalog1:5001
[FRONTEND] info(5) -> CACHE MISS -> http://catalog2:5001
[FRONTEND] info(5) -> CACHE HIT
[FRONTEND] info(5) -> CACHE HIT
[FRONTEND] purchase(5) -> http://order1:5002
[FRONTEND] Cache invalidated for item 5
[FRONTEND] info(5) -> CACHE MISS -> http://catalog1:5001
[FRONTEND] search("distributed systems") -> http://catalog2:5001
[FRONTEND] search("undergraduate school") -> http://catalog1:5001
[FRONTEND] search("distributed systems") -> http://catalog2:5001
[FRONTEND] search("undergraduate school") -> http://catalog1:5001
[FRONTEND] search("distributed systems") -> http://catalog2:5001
[FRONTEND] search("undergraduate school") -> http://catalog1:5001
[FRONTEND] purchase(6) -> http://order1:5002
[FRONTEND] purchase(7) -> http://order2:5002
[FRONTEND] purchase(6) -> http://order1:5002
[FRONTEND] purchase(7) -> http://order2:5002
[FRONTEND] Cache invalidated for item 6
[FRONTEND] Cache invalidated for item 7
[FRONTEND] Cache invalidated for item 6
[FRONTEND] Cache invalidated for item 7
```

#### bazar_order1 (Lab 2 relevant entries — shows round-robin purchases)
```
[ORDER] purchase(5) -> catalog at http://catalog1:5001
[ORDER] bought book "How to finish Project 3 on time"
[ORDER] Synced order "How to finish Project 3 on time" to peer http://order2:5002
[ORDER] purchase(6) -> catalog at http://catalog1:5001
[ORDER] bought book "Why theory classes are so hard"
[ORDER] Synced order "Why theory classes are so hard" to peer http://order2:5002
[ORDER] purchase(6) -> catalog at http://catalog1:5001
[ORDER] bought book "Why theory classes are so hard"
[ORDER] Synced order "Why theory classes are so hard" to peer http://order2:5002
```

#### bazar_order2 (Lab 2 relevant entries — receives alternating purchases + sync records)
```
[ORDER] purchase(7) -> catalog at http://catalog2:5001
[ORDER] bought book "Spring in the Pioneer Valley"
[ORDER] Synced order "Spring in the Pioneer Valley" to peer http://order1:5002
[ORDER] Received sync order for "How to finish Project 3 on time" from peer.
[ORDER] Received sync order for "Why theory classes are so hard" from peer.
[ORDER] Received sync order for "Why theory classes are so hard" from peer.
[ORDER] purchase(7) -> catalog at http://catalog2:5001
[ORDER] bought book "Spring in the Pioneer Valley"
[ORDER] Received sync order for "Spring in the Pioneer Valley" from peer.
[ORDER] Purchase failed: "Spring in the Pioneer Valley" is out of stock.
```
