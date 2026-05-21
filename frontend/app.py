"""
Bazar.com — Frontend API Gateway
================================
A stateless Flask service that:
  * Exposes the client-facing REST API on port 5000.
  * Round-robins requests across catalog and order replicas (simple LB).
  * Maintains an in-memory LRU cache for /info responses.
  * Accepts server-push invalidations from catalog replicas to keep the
    cache consistent with the underlying data.

Design notes
------------
- Cache keys are ALWAYS stored as strings. Flask routes pass `item_id` as an
  int (via the <int:...> converter), but invalidation messages may arrive as
  JSON where the id can be a string. Normalising to `str(item_id)` everywhere
  guarantees lookups, inserts, and deletions hit the same bucket.
- All log statements use `print(..., flush=True)` so Docker's log driver
  shows them immediately, instead of waiting for stdout to fill its buffer.
- Thread safety is preserved via `_cache_lock` (LRU state) and `_rr_lock`
  (round-robin counters); both are kept exactly as in the original design.
"""

import os
import sys
import time
import threading
from collections import OrderedDict

import requests
from flask import Flask, jsonify

# Force stdout/stderr to flush immediately so logs appear in real time
# under `docker compose up` (Python defaults to block buffering on a pipe).
sys.stdout.reconfigure(line_buffering=True)
sys.stderr.reconfigure(line_buffering=True)

app = Flask(__name__)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

# Comma-separated lists of replica URLs, configurable via environment.
CATALOG_REPLICAS = os.environ.get(
    'CATALOG_REPLICAS', 'http://catalog:5001'
).split(',')
ORDER_REPLICAS = os.environ.get(
    'ORDER_REPLICAS', 'http://order:5002'
).split(',')

REQUEST_TIMEOUT_SECONDS = 5
MAX_CACHE_SIZE = 100

LOG_PREFIX = '[FRONTEND]'


def log(message: str) -> None:
    """Single entry point for structured, flushed logging."""
    print(f'{LOG_PREFIX} {message}', flush=True)


# ---------------------------------------------------------------------------
# LRU Cache (thread-safe)
# Keys are always normalised to `str` to avoid int/str mismatches between
# Flask route params and JSON payloads.
# ---------------------------------------------------------------------------

_cache: "OrderedDict[str, dict]" = OrderedDict()
_cache_lock = threading.Lock()


def _key(item_id) -> str:
    """Canonical cache-key form: always a string."""
    return str(item_id)


def cache_get(item_id):
    """Return the cached value for `item_id`, or None on a miss.

    On a hit the entry is moved to the MRU end of the OrderedDict.
    """
    key = _key(item_id)
    with _cache_lock:
        if key in _cache:
            _cache.move_to_end(key)
            return _cache[key]
    return None


def cache_put(item_id, data) -> None:
    """Insert/update `item_id` in the cache, evicting the LRU entry if full."""
    key = _key(item_id)
    with _cache_lock:
        _cache[key] = data
        _cache.move_to_end(key)
        if len(_cache) > MAX_CACHE_SIZE:
            evicted_key, _ = _cache.popitem(last=False)
            log(f'Cache evicted LRU entry for item {evicted_key}')


def cache_delete(item_id) -> bool:
    """Remove `item_id` from the cache. Returns True if an entry was removed."""
    key = _key(item_id)
    with _cache_lock:
        existed = _cache.pop(key, None) is not None
    if existed:
        log(f'Cache invalidated for item {key}')
    else:
        log(f'Cache invalidation requested for item {key} (no entry present)')
    return existed


# ---------------------------------------------------------------------------
# Round-robin load balancer (thread-safe)
# ---------------------------------------------------------------------------

_catalog_idx = 0
_order_idx = 0
_rr_lock = threading.Lock()


def next_catalog() -> str:
    """Return the next catalog replica URL in round-robin order."""
    global _catalog_idx
    with _rr_lock:
        url = CATALOG_REPLICAS[_catalog_idx % len(CATALOG_REPLICAS)]
        _catalog_idx += 1
    return url


def next_order() -> str:
    """Return the next order replica URL in round-robin order."""
    global _order_idx
    with _rr_lock:
        url = ORDER_REPLICAS[_order_idx % len(ORDER_REPLICAS)]
        _order_idx += 1
    return url


# ---------------------------------------------------------------------------
# HTTP proxy helpers
# Centralises timeout handling, JSON decoding, and error mapping so the
# route handlers stay short and intent-revealing (Single Responsibility).
# ---------------------------------------------------------------------------

def _safe_json(resp):
    """Return the JSON body of `resp`, or a structured error if it isn't JSON."""
    try:
        return resp.json()
    except ValueError:
        return {'error': 'Upstream returned a non-JSON response',
                'body':  resp.text[:200]}


def _proxy_get(url):
    """Forward a GET request to `url` and translate transport errors to HTTP."""
    try:
        resp = requests.get(url, timeout=REQUEST_TIMEOUT_SECONDS)
        return jsonify(_safe_json(resp)), resp.status_code
    except requests.exceptions.ConnectionError as exc:
        log(f'GET {url} -> ConnectionError: {exc}')
        return jsonify({'error': 'Backend unavailable', 'detail': str(exc)}), 503
    except requests.exceptions.Timeout as exc:
        log(f'GET {url} -> Timeout: {exc}')
        return jsonify({'error': 'Backend timeout', 'detail': str(exc)}), 504
    except requests.exceptions.RequestException as exc:
        log(f'GET {url} -> RequestException: {exc}')
        return jsonify({'error': 'Upstream request failed', 'detail': str(exc)}), 502


def _proxy_post(url):
    """Forward a POST request to `url` and translate transport errors to HTTP."""
    try:
        resp = requests.post(url, timeout=REQUEST_TIMEOUT_SECONDS)
        return jsonify(_safe_json(resp)), resp.status_code
    except requests.exceptions.ConnectionError as exc:
        log(f'POST {url} -> ConnectionError: {exc}')
        return jsonify({'error': 'Backend unavailable', 'detail': str(exc)}), 503
    except requests.exceptions.Timeout as exc:
        log(f'POST {url} -> Timeout: {exc}')
        return jsonify({'error': 'Backend timeout', 'detail': str(exc)}), 504
    except requests.exceptions.RequestException as exc:
        log(f'POST {url} -> RequestException: {exc}')
        return jsonify({'error': 'Upstream request failed', 'detail': str(exc)}), 502


# ---------------------------------------------------------------------------
# Client-facing endpoints
# ---------------------------------------------------------------------------

@app.route('/search/<path:topic>', methods=['GET'])
def search(topic):
    """
    Search books by topic. Load-balanced across catalog replicas.
    Search results are intentionally not cached: low repetition and the
    underlying catalog can change at any moment.

    Example: GET /search/distributed%20systems
    """
    catalog_url = next_catalog()
    log(f'search("{topic}") -> {catalog_url}')
    return _proxy_get(f'{catalog_url}/search/{topic}')


@app.route('/info/<int:item_id>', methods=['GET'])
def info(item_id):
    """
    Return full details for a single book.

    Flow:
      1. Look the item up in the LRU cache (string-normalised key).
      2. On a hit, return immediately.
      3. On a miss, fetch from the next catalog replica and, if the upstream
         response was successful, populate the cache.

    Each branch records its own internal execution time (in milliseconds) so
    that the cache speedup can be observed directly in the server logs.

    Example: GET /info/2
    """
    # Start the per-request benchmark clock as early as possible so the
    # measurement reflects everything the handler does, including the cache
    # lookup itself.
    start_time = time.time()

    cached = cache_get(item_id)
    with _cache_lock:
        cache_size = len(_cache)

    # ---------------- CACHE HIT path ----------------
    if cached is not None:
        duration = (time.time() - start_time) * 1000  # milliseconds
        log(
            f'>>> CACHE HIT  <<<  info({item_id}) '
            f'[Internal Time: {duration:.4f} ms] '
            f'[cache size = {cache_size}]'
        )
        return jsonify(cached), 200

    # ---------------- CACHE MISS path ----------------
    catalog_url = next_catalog()
    log(
        f'### CACHE MISS ###  info({item_id}) -> fetching from {catalog_url} '
        f'[cache size = {cache_size}]'
    )

    try:
        resp = requests.get(
            f'{catalog_url}/info/{item_id}',
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
    except requests.exceptions.ConnectionError as exc:
        duration = (time.time() - start_time) * 1000
        log(f'info({item_id}) -> ConnectionError after {duration:.4f} ms: {exc}')
        return jsonify({'error': 'Backend unavailable', 'detail': str(exc)}), 503
    except requests.exceptions.Timeout as exc:
        duration = (time.time() - start_time) * 1000
        log(f'info({item_id}) -> Timeout after {duration:.4f} ms: {exc}')
        return jsonify({'error': 'Backend timeout', 'detail': str(exc)}), 504
    except requests.exceptions.RequestException as exc:
        duration = (time.time() - start_time) * 1000
        log(f'info({item_id}) -> RequestException after {duration:.4f} ms: {exc}')
        return jsonify({'error': 'Upstream request failed', 'detail': str(exc)}), 502

    data = _safe_json(resp)
    if resp.status_code == 200:
        cache_put(item_id, data)

    # Total elapsed time covers cache lookup + network fetch + cache write.
    duration = (time.time() - start_time) * 1000
    log(
        f'### CACHE MISS ###  info({item_id}) -> fetched from {catalog_url} '
        f'[Internal Time: {duration:.4f} ms]'
    )

    return jsonify(data), resp.status_code


@app.route('/purchase/<int:item_id>', methods=['POST'])
def purchase(item_id):
    """
    Purchase a book by item number. Load-balanced across order replicas.
    Stock and order state are owned by the catalog/order services; this
    endpoint is a thin pass-through that just picks a replica.

    Example: POST /purchase/2
    """
    order_url = next_order()
    log(f'purchase({item_id}) -> {order_url}')
    return _proxy_post(f'{order_url}/purchase/{item_id}')


# ---------------------------------------------------------------------------
# Cache consistency endpoint (server-push invalidation)
# ---------------------------------------------------------------------------

@app.route('/invalidate/<int:item_id>', methods=['POST'])
def invalidate(item_id):
    """
    Invalidation hook called by catalog replicas before they write to their
    database. Drops the cached `/info` entry for `item_id` so the next call
    fetches fresh data.

    Always returns 200; cache invalidation is idempotent and a missing entry
    is not considered an error.
    """
    cache_delete(item_id)
    return jsonify({'success': True, 'item_id': item_id}), 200


# ---------------------------------------------------------------------------
# Operational endpoint
# ---------------------------------------------------------------------------

@app.route('/health', methods=['GET'])
def health():
    """Lightweight liveness probe for Docker/k8s healthchecks."""
    with _cache_lock:
        cache_size = len(_cache)
    return jsonify({
        'status':            'ok',
        'cache_size':        cache_size,
        'catalog_replicas':  CATALOG_REPLICAS,
        'order_replicas':    ORDER_REPLICAS,
    }), 200


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------

if __name__ == '__main__':
    log(f'Starting frontend with catalog replicas: {CATALOG_REPLICAS}')
    log(f'Starting frontend with order   replicas: {ORDER_REPLICAS}')
    log(f'LRU cache capacity: {MAX_CACHE_SIZE} entries')
    app.run(host='0.0.0.0', port=5000, threaded=True)
