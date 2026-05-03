# Bazar.com — Actual Program Output

The following is the real output captured from running `python client/client.py`
against the three live Docker containers (`bazar_catalog`, `bazar_order`, `bazar_frontend`).

---

## Client Output

```
##############################################################
  Bazar.com Test Client
  Connecting to: http://localhost:5000
##############################################################

==============================================================
  SEARCH  topic = "distributed systems"
==============================================================
  ID     Title
  ----   ---------------------------------------------
  [1]    How to get a good grade in DOS in 40 minutes a day
  [2]    RPCs for Noobs

==============================================================
  SEARCH  topic = "undergraduate school"
==============================================================
  ID     Title
  ----   ---------------------------------------------
  [3]    Xen and the Art of Surviving Undergraduate School
  [4]    Cooking for the Impatient Undergrad

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
  [FAIL]  Failed: Item 99 not found

==============================================================
  All tests complete.
==============================================================
```

---

## Server Logs (docker-compose logs)

### bazar_frontend
```
[FRONTEND] search("distributed systems") -> catalog
[FRONTEND] search("undergraduate school") -> catalog
[FRONTEND] search("cooking") -> catalog
[FRONTEND] info(1) -> catalog
[FRONTEND] info(2) -> catalog
[FRONTEND] info(3) -> catalog
[FRONTEND] info(4) -> catalog
[FRONTEND] info(99) -> catalog
[FRONTEND] purchase(1) -> order
[FRONTEND] purchase(2) -> order
[FRONTEND] purchase(3) -> order
[FRONTEND] info(1) -> catalog
[FRONTEND] info(2) -> catalog
[FRONTEND] purchase(99) -> order
```

### bazar_catalog
```
[CATALOG] Database seeded with 4 books.
[CATALOG] search("distributed systems") -> 2 results
[CATALOG] search("undergraduate school") -> 2 results
[CATALOG] search("cooking") -> 0 results
[CATALOG] info(1) -> {'title': 'How to get a good grade in DOS in 40 minutes a day', 'quantity': 10, 'price': 30.0}
[CATALOG] info(2) -> {'title': 'RPCs for Noobs', 'quantity': 10, 'price': 25.0}
[CATALOG] info(3) -> {'title': 'Xen and the Art of Surviving Undergraduate School', 'quantity': 10, 'price': 40.0}
[CATALOG] info(4) -> {'title': 'Cooking for the Impatient Undergrad', 'quantity': 10, 'price': 20.0}
[CATALOG] update(1) with {'quantity': -1}
[CATALOG] update(2) with {'quantity': -1}
[CATALOG] update(3) with {'quantity': -1}
[CATALOG] info(1) -> {'title': 'How to get a good grade in DOS in 40 minutes a day', 'quantity': 9, 'price': 30.0}
[CATALOG] info(2) -> {'title': 'RPCs for Noobs', 'quantity': 9, 'price': 25.0}
```

### bazar_order
```
[ORDER] Order database ready.
[ORDER] bought book "How to get a good grade in DOS in 40 minutes a day"
[ORDER] bought book "RPCs for Noobs"
[ORDER] bought book "Xen and the Art of Surviving Undergraduate School"
[ORDER] Purchase failed: item 99 not found in catalog.
```
