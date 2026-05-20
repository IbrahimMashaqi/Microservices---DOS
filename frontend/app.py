"""
Bazar.com - Front-End Server
Single entry point for all client requests.

Lab 2 additions:
  - In-memory LRU cache for book info (GET /info) responses
  - Round-robin load balancing across catalog and order replicas
  - POST /invalidate/<id> endpoint for server-push cache consistency
Runs on port 5000.
"""

import os
import threading
from collections import OrderedDict

import requests
from flask import Flask, jsonify

app = Flask(__name__)

# Comma-separated replica lists — configurable via environment variables
CATALOG_REPLICAS = os.environ.get(
    'CATALOG_REPLICAS', 'http://catalog:5001'
).split(',')
ORDER_REPLICAS = os.environ.get(
    'ORDER_REPLICAS', 'http://order:5002'
).split(',')


# -----------------------------------------------------------------------
# LRU In-Memory Cache
# Stores item_id -> {title, quantity, price} for recent /info lookups.
# Capacity-bounded with LRU eviction; protected by a threading.Lock.
# -----------------------------------------------------------------------

MAX_CACHE_SIZE = 100
_cache      = OrderedDict()
_cache_lock = threading.Lock()


def cache_get(item_id):
    """Return cached data for item_id, or None on a miss. Marks as recently used."""
    with _cache_lock:
        if item_id in _cache:
            _cache.move_to_end(item_id)
            return _cache[item_id]
    return None


def cache_put(item_id, data):
    """Store data for item_id, evicting the LRU entry when over capacity."""
    with _cache_lock:
        _cache[item_id] = data
        _cache.move_to_end(item_id)
        if len(_cache) > MAX_CACHE_SIZE:
            _cache.popitem(last=False)


def cache_delete(item_id):
    """Remove item_id from cache (used by invalidation endpoint)."""
    with _cache_lock:
        _cache.pop(item_id, None)
    print(f'[FRONTEND] Cache invalidated for item {item_id}')


# -----------------------------------------------------------------------
# Round-Robin Load Balancer
# Distributes requests across all healthy replicas for each service.
# -----------------------------------------------------------------------

_catalog_idx = 0
_order_idx   = 0
_rr_lock     = threading.Lock()


def next_catalog():
    """Return the next catalog replica URL (round-robin)."""
    global _catalog_idx
    with _rr_lock:
        url = CATALOG_REPLICAS[_catalog_idx % len(CATALOG_REPLICAS)]
        _catalog_idx += 1
    return url


def next_order():
    """Return the next order replica URL (round-robin)."""
    global _order_idx
    with _rr_lock:
        url = ORDER_REPLICAS[_order_idx % len(ORDER_REPLICAS)]
        _order_idx += 1
    return url


# -----------------------------------------------------------------------
# Helper proxies
# -----------------------------------------------------------------------

def _proxy_get(url):
    try:
        resp = requests.get(url, timeout=5)
        return jsonify(resp.json()), resp.status_code
    except requests.exceptions.ConnectionError as e:
        return jsonify({'error': f'Backend unavailable: {e}'}), 503


def _proxy_post(url):
    try:
        resp = requests.post(url, timeout=5)
        return jsonify(resp.json()), resp.status_code
    except requests.exceptions.ConnectionError as e:
        return jsonify({'error': f'Backend unavailable: {e}'}), 503


# -----------------------------------------------------------------------
# Client-facing Endpoints
# -----------------------------------------------------------------------

@app.route('/search/<path:topic>', methods=['GET'])
def search(topic):
    """
    Search books by topic. Load-balanced across catalog replicas.
    Search results are not cached (low repetition, subject to catalog changes).
    Example: GET /search/distributed%20systems
    """
    catalog_url = next_catalog()
    print(f'[FRONTEND] search("{topic}") -> {catalog_url}')
    return _proxy_get(f'{catalog_url}/search/{topic}')


@app.route('/info/<int:item_id>', methods=['GET'])
def info(item_id):
    """
    Get full details for a book by item number.
    Checks the in-memory cache first; on a miss, fetches from a catalog replica
    and populates the cache.
    Example: GET /info/2
    """
    cached = cache_get(item_id)
    if cached:
        print(f'[FRONTEND] info({item_id}) -> CACHE HIT')
        return jsonify(cached), 200

    catalog_url = next_catalog()
    print(f'[FRONTEND] info({item_id}) -> CACHE MISS -> {catalog_url}')
    try:
        resp = requests.get(f'{catalog_url}/info/{item_id}', timeout=5)
        data = resp.json()
        if resp.status_code == 200:
            cache_put(item_id, data)
        return jsonify(data), resp.status_code
    except requests.exceptions.ConnectionError as e:
        return jsonify({'error': f'Backend unavailable: {e}'}), 503


@app.route('/purchase/<int:item_id>', methods=['POST'])
def purchase(item_id):
    """
    Purchase a book by item number. Load-balanced across order replicas.
    Example: POST /purchase/2
    """
    order_url = next_order()
    print(f'[FRONTEND] purchase({item_id}) -> {order_url}')
    return _proxy_post(f'{order_url}/purchase/{item_id}')


# -----------------------------------------------------------------------
# Cache Consistency Endpoint (server-push invalidation)
# -----------------------------------------------------------------------

@app.route('/invalidate/<int:item_id>', methods=['POST'])
def invalidate(item_id):
    """
    Called by catalog replicas before they write to their database.
    Removes the stale cache entry so the next /info request fetches fresh data.
    """
    cache_delete(item_id)
    return jsonify({'success': True}), 200


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, threaded=True)
