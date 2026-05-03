"""
Bazar.com - Test Client
Exercises all three front-end REST endpoints (search, info, purchase)
and prints results in a clearly formatted manner.

Usage:
    python client.py [--host HOST] [--port PORT]

Defaults to http://localhost:5000 (Docker-exposed front-end port).
"""

import sys
import json
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


# -----------------------------------------------------------------------
# Pretty-print helpers
# -----------------------------------------------------------------------

DIVIDER = '=' * 62

def header(title):
    print(f'\n{DIVIDER}')
    print(f'  {title}')
    print(DIVIDER)


def print_json(data):
    """Print a JSON-serialisable object with indentation."""
    print(json.dumps(data, indent=4))


# -----------------------------------------------------------------------
# API wrappers
# -----------------------------------------------------------------------

def search(base_url, topic):
    """GET /search/<topic> — find books by subject."""
    header(f'SEARCH  topic = "{topic}"')
    try:
        resp = requests.get(f'{base_url}/search/{topic}', timeout=5)
        data = resp.json()
    except requests.exceptions.ConnectionError:
        print('  [ERROR] Could not connect to front-end server.')
        return

    if not data:
        print('  No books found for this topic.')
    else:
        print(f'  {"ID":<6} {"Title"}')
        print(f'  {"-"*4}   {"-"*45}')
        for book in data:
            print(f'  [{book["id"]}]    {book["title"]}')

    return data


def info(base_url, item_id):
    """GET /info/<id> — get full details for a book."""
    header(f'INFO    item_id = {item_id}')
    try:
        resp = requests.get(f'{base_url}/info/{item_id}', timeout=5)
        data = resp.json()
    except requests.exceptions.ConnectionError:
        print('  [ERROR] Could not connect to front-end server.')
        return

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
        resp = requests.post(f'{base_url}/purchase/{item_id}', timeout=5)
        data = resp.json()
    except requests.exceptions.ConnectionError:
        print('  [ERROR] Could not connect to front-end server.')
        return

    if data.get('success'):
        print(f'  [OK]  {data["message"]}')
    else:
        print(f'  [FAIL]  Failed: {data.get("error", "Unknown error")}')

    return data


# -----------------------------------------------------------------------
# Main test scenario
# -----------------------------------------------------------------------

def run_tests(base_url):
    print(f'\n{"#"*62}')
    print(f'  Bazar.com Test Client')
    print(f'  Connecting to: {base_url}')
    print(f'{"#"*62}')

    # --- Search ---
    search(base_url, 'distributed systems')
    search(base_url, 'undergraduate school')
    search(base_url, 'cooking')           # topic with no results

    # --- Info for all 4 books ---
    for item_id in range(1, 5):
        info(base_url, item_id)

    info(base_url, 99)                    # non-existent item

    # --- Purchases ---
    purchase(base_url, 1)   # should succeed
    purchase(base_url, 2)   # should succeed
    purchase(base_url, 3)   # should succeed

    # Verify stock decreased
    info(base_url, 1)
    info(base_url, 2)

    # Attempt to buy a non-existent book
    purchase(base_url, 99)

    print(f'\n{DIVIDER}')
    print('  All tests complete.')
    print(DIVIDER + '\n')


if __name__ == '__main__':
    args = parse_args()
    base_url = f'http://{args.host}:{args.port}'
    run_tests(base_url)
