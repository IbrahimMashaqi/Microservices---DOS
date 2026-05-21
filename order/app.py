
import os
import sqlite3
import threading
from datetime import datetime, timezone

import requests
from flask import Flask, jsonify, request

app = Flask(__name__)

DB_PATH = os.environ.get('DB_PATH', '/data/orders.db')
db_lock = threading.Lock()

# Comma-separated list of catalog replica URLs
CATALOG_REPLICAS = os.environ.get(
    'CATALOG_REPLICAS', 'http://catalog:5001'
).split(',')

# Peer order replica URL for order log synchronization
PEER_URL = os.environ.get('PEER_URL', '')

# Round-robin state for catalog replica selection
_catalog_idx  = 0
_catalog_lock = threading.Lock()


def next_catalog_url():
    """Return the next catalog replica URL using round-robin."""
    global _catalog_idx
    with _catalog_lock:
        url = CATALOG_REPLICAS[_catalog_idx % len(CATALOG_REPLICAS)]
        _catalog_idx += 1
    return url


def get_db():
    """Open a new SQLite connection for this request."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Create the orders table if it does not already exist."""
    with db_lock:
        conn = get_db()
        c = conn.cursor()
        c.execute('''
            CREATE TABLE IF NOT EXISTS orders (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                book_id    INTEGER NOT NULL,
                book_title TEXT    NOT NULL,
                timestamp  TEXT    NOT NULL
            )
        ''')
        conn.commit()
        conn.close()
    print('[ORDER] Order database ready.')


def sync_order_to_peer(book_id, book_title, timestamp):
    """Replicate a completed order record to the peer order replica."""
    if not PEER_URL:
        return
    try:
        requests.post(
            f'{PEER_URL}/sync_order',
            json={
                'book_id':    book_id,
                'book_title': book_title,
                'timestamp':  timestamp,
            },
            timeout=2
        )
        print(f'[ORDER] Synced order "{book_title}" to peer {PEER_URL}')
    except Exception:
        pass  # best-effort replication


# -------------------------------------------------------------------
# Endpoints
# -------------------------------------------------------------------

@app.route('/health', methods=['GET'])
def health():
    return jsonify({'status': 'ok'}), 200


@app.route('/purchase/<int:item_id>', methods=['POST'])
def purchase(item_id):
    
    catalog_url = next_catalog_url()
    print(f'[ORDER] purchase({item_id}) -> catalog at {catalog_url}')

    # Step 1 — Verify stock
    try:
        catalog_resp = requests.get(f'{catalog_url}/info/{item_id}', timeout=5)
    except requests.exceptions.ConnectionError:
        return jsonify({'error': 'Catalog service is unavailable'}), 503

    if catalog_resp.status_code == 404:
        print(f'[ORDER] Purchase failed: item {item_id} not found in catalog.')
        return jsonify({'success': False, 'error': f'Item {item_id} not found'}), 404

    book_info = catalog_resp.json()

    # Step 2 — Reject if out of stock
    if book_info.get('quantity', 0) <= 0:
        print(f'[ORDER] Purchase failed: "{book_info["title"]}" is out of stock.')
        return jsonify({
            'success': False,
            'error':   f'"{book_info["title"]}" is out of stock',
        }), 400

    # Step 3 — Decrement stock (catalog will invalidate cache + sync to peer)
    try:
        update_resp = requests.put(
            f'{catalog_url}/update/{item_id}',
            json={'quantity': -1},
            timeout=5
        )
        if update_resp.status_code != 200:
            return jsonify({'error': 'Failed to update catalog stock'}), 500
    except requests.exceptions.ConnectionError:
        return jsonify({'error': 'Catalog service is unavailable'}), 503

    # Step 4 — Persist and replicate the order
    timestamp = datetime.now(timezone.utc).isoformat()
    with db_lock:
        conn = get_db()
        c = conn.cursor()
        c.execute(
            'INSERT INTO orders (book_id, book_title, timestamp) VALUES (?, ?, ?)',
            (item_id, book_info['title'], timestamp)
        )
        conn.commit()
        conn.close()

    sync_order_to_peer(item_id, book_info['title'], timestamp)

    print(f'[ORDER] bought book "{book_info["title"]}"')
    return jsonify({
        'success': True,
        'message': f'bought book {book_info["title"]}',
    }), 200


@app.route('/sync_order', methods=['POST'])
def sync_order():
    """
    Receive a replicated order entry from the peer order server.
    Inserts the record directly into the local orders table.
    """
    data = request.get_json(force=True)
    if not data:
        return jsonify({'error': 'No JSON body'}), 400

    with db_lock:
        conn = get_db()
        c = conn.cursor()
        c.execute(
            'INSERT INTO orders (book_id, book_title, timestamp) VALUES (?, ?, ?)',
            (data['book_id'], data['book_title'], data['timestamp'])
        )
        conn.commit()
        conn.close()

    print(f'[ORDER] Received sync order for "{data["book_title"]}" from peer.')
    return jsonify({'success': True}), 200


if __name__ == '__main__':
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    init_db()
    app.run(host='0.0.0.0', port=5002, threaded=True)
