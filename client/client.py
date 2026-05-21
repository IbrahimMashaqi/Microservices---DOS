
import json
import time
import argparse

import requests

# -----------------------------------------------------------------------
# Configuration
# -----------------------------------------------------------------------

def parse_args():
    parser = argparse.ArgumentParser(description='Bazar.com Test Client')
    parser.add_argument('--host', default='localhost', help='Front-end server host')
    parser.add_argument('--port', default=5000, type=int, help='Front-end server port')
    return parser.parse_args()


# Persistent session — reuses the TCP connection across all requests so that
# cache-hit latency (no backend call) is clearly distinguishable from
# cache-miss latency (extra hop to the catalog).
session = requests.Session()


# -----------------------------------------------------------------------
# Pretty-print helpers
# -----------------------------------------------------------------------

DIVIDER = '=' * 62

def header(title):
    print(f'\n{DIVIDER}')
    print(f'  {title}')
    print(DIVIDER)


# -----------------------------------------------------------------------
# API wrappers
# -----------------------------------------------------------------------

def search(base_url, topic):
    """GET /search/<topic> — find books by subject."""
    header(f'SEARCH  topic = "{topic}"')
    try:
        resp = session.get(f'{base_url}/search/{topic}', timeout=5)
        data = resp.json()
    except requests.exceptions.ConnectionError:
        print('  [ERROR] Could not connect to front-end server.')
        return None

    if not data:
        print('  No books found for this topic.')
    else:
        print(f'  {"ID":<6} {"Title"}')
        print(f'  {"-"*4}   {"-"*50}')
        for book in data:
            print(f'  [{book["id"]}]    {book["title"]}')

    return data


def info(base_url, item_id):
    """GET /info/<id> — get full details for a book."""
    header(f'INFO    item_id = {item_id}')
    try:
        resp = session.get(f'{base_url}/info/{item_id}', timeout=5)
        data = resp.json()
    except requests.exceptions.ConnectionError:
        print('  [ERROR] Could not connect to front-end server.')
        return None

    if resp.status_code == 404 or 'error' in data:
        print(f'  [NOT FOUND] {data.get("error", "Unknown error")}')
    else:
        print(f'  Title    : {data["title"]}')
        print(f'  Price    : ${data["price"]:.2f}')
        print(f'  In Stock : {data["quantity"]} copies')

    return data


def purchase(base_url, item_id):
    """POST /purchase/<id> — buy a book."""
    header(f'PURCHASE item_id = {item_id}')
    try:
        resp = session.post(f'{base_url}/purchase/{item_id}', timeout=5)
        data = resp.json()
    except requests.exceptions.ConnectionError:
        print('  [ERROR] Could not connect to front-end server.')
        return None

    if data.get('success'):
        print(f'  [OK]  {data["message"]}')
    else:
        print(f'  [FAIL]  {data.get("error", "Unknown error")}')

    return data


def timed_info(base_url, item_id):
    """GET /info/<id> and return (data, elapsed_ms). Used for cache benchmarking."""
    try:
        t0   = time.perf_counter()
        resp = session.get(f'{base_url}/info/{item_id}', timeout=5)
        ms   = (time.perf_counter() - t0) * 1000
        return resp.json(), ms
    except requests.exceptions.ConnectionError:
        return None, 0.0


# -----------------------------------------------------------------------
# Lab 1: Core functionality tests
# -----------------------------------------------------------------------

def run_lab1_tests(base_url):
    print(f'\n{"#"*62}')
    print(f'  LAB 1 — Core Functionality Tests')
    print(f'  Connecting to: {base_url}')
    print(f'{"#"*62}')

    # Search
    search(base_url, 'distributed systems')
    search(base_url, 'undergraduate school')
    search(base_url, 'cooking')            # topic with no results

    # Info for all 4 original books
    for item_id in range(1, 5):
        info(base_url, item_id)

    info(base_url, 99)                     # non-existent item

    # Purchases
    purchase(base_url, 1)
    purchase(base_url, 2)
    purchase(base_url, 3)

    # Verify stock decremented
    info(base_url, 1)
    info(base_url, 2)

    # Purchase a non-existent book
    purchase(base_url, 99)

    print(f'\n{DIVIDER}')
    print('  Lab 1 tests complete.')
    print(DIVIDER)


# -----------------------------------------------------------------------
# Lab 2: New books, caching, cache consistency, load balancing
# -----------------------------------------------------------------------

def run_lab2_tests(base_url):
    print(f'\n{"#"*62}')
    print(f'  LAB 2 — Caching, Consistency & Load Balancing Tests')
    print(f'{"#"*62}')

    # ------------------------------------------------------------------
    # 1. New books (IDs 5-7 added in Lab 2)
    # ------------------------------------------------------------------
    header('NEW BOOKS — Lab 2 catalog additions (IDs 5-7)')
    search(base_url, 'distributed systems')   # should now include book 5
    search(base_url, 'undergraduate school')  # should now include books 6 & 7
    for item_id in range(5, 8):
        info(base_url, item_id)

    # ------------------------------------------------------------------
    # 2. Cache hit / miss timing
    # ------------------------------------------------------------------
    header('CACHE TEST — Same item queried twice (expect hit on 2nd request)')
    data1, t1 = timed_info(base_url, 5)
    print(f'  1st request (CACHE MISS) : {t1:6.2f} ms  '
          f'-> {data1.get("title", "?") if data1 else "error"}')

    data2, t2 = timed_info(base_url, 5)
    print(f'  2nd request (CACHE HIT)  : {t2:6.2f} ms  '
          f'-> {data2.get("title", "?") if data2 else "error"}')

    if t1 > 0 and t2 > 0:
        speedup = t1 / t2
        print(f'  Cache speedup            : {speedup:.1f}x faster')
    print('  (Check server logs for [CACHE HIT] / [CACHE MISS] confirmation)')

    # ------------------------------------------------------------------
    # 3. Cache consistency — purchase triggers invalidation
    # ------------------------------------------------------------------
    header('CACHE CONSISTENCY — Purchase should invalidate cached stock')
    data_before, t_before = timed_info(base_url, 5)
    stock_before = data_before.get('quantity', '?') if data_before else '?'
    print(f'  info(5) before purchase  : {t_before:6.2f} ms  stock={stock_before}')

    purchase(base_url, 5)
    print('  [Server should have sent POST /invalidate/5 to front-end]')

    data_after, t_after = timed_info(base_url, 5)
    stock_after = data_after.get('quantity', '?') if data_after else '?'
    print(f'  info(5) after  purchase  : {t_after:6.2f} ms  stock={stock_after}')
    print(f'  Stock decreased: {stock_before} -> {stock_after}  (cache miss fetched fresh data)')

    # ------------------------------------------------------------------
    # 4. Load balancing — multiple requests spread across replicas
    # ------------------------------------------------------------------
    header('LOAD BALANCING — 6 search requests distributed across catalog replicas')
    topics = ['distributed systems', 'undergraduate school'] * 3
    for i, topic in enumerate(topics, start=1):
        resp = session.get(f'{base_url}/search/{topic}', timeout=5)
        count = len(resp.json()) if resp.status_code == 200 else 0
        print(f'  Request {i}: search("{topic}") -> {count} results  '
              f'(check server log for which replica served it)')

    header('LOAD BALANCING — 4 purchases distributed across order replicas')
    for item_id in [6, 7, 6, 7]:
        purchase(base_url, item_id)
        print('  (check server log for which order replica processed this)')

    # ------------------------------------------------------------------
    # 5. Out-of-stock test for new books
    # ------------------------------------------------------------------
    header('OUT-OF-STOCK TEST — Drain book 7 and verify failure')
    # First check current stock
    data, _ = timed_info(base_url, 7)
    remaining = data.get('quantity', 0) if data else 0
    print(f'  Book 7 current stock: {remaining} copies')
    for _ in range(remaining):
        purchase(base_url, 7)
    result = purchase(base_url, 7)  # this one should fail
    if result and not result.get('success'):
        print('  Correctly rejected: out-of-stock handling works.')

    print(f'\n{DIVIDER}')
    print('  Lab 2 tests complete.')
    print(DIVIDER)


# -----------------------------------------------------------------------
# Main
# -----------------------------------------------------------------------

if __name__ == '__main__':
    args     = parse_args()
    base_url = f'http://{args.host}:{args.port}'

    run_lab1_tests(base_url)
    run_lab2_tests(base_url)

    print(f'\n{"#"*62}')
    print('  All tests complete.')
    print(f'{"#"*62}\n')
