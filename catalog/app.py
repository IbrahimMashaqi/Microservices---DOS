
import os
import sqlite3
import threading

import requests
from flask import Flask, jsonify, request

app = Flask(__name__)

DB_PATH = os.environ.get('DB_PATH', '/data/catalog.db')
db_lock = threading.Lock()

# Peer replica URL — set via env var; empty string means standalone mode
PEER_URL     = os.environ.get('PEER_URL',     '')
# Front-end URL for server-push cache invalidation
FRONTEND_URL = os.environ.get('FRONTEND_URL', '')


def get_db():
    """Open a per-call SQLite connection (SQLite is not safe to share across threads)."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Create the books table and seed it with all seven books on first run."""
    with db_lock:
        conn = get_db()
        c = conn.cursor()
        c.execute('''
            CREATE TABLE IF NOT EXISTS books (
                id       INTEGER PRIMARY KEY,
                title    TEXT    NOT NULL,
                topic    TEXT    NOT NULL,
                quantity INTEGER NOT NULL DEFAULT 10,
                price    REAL    NOT NULL
            )
        ''')
        c.execute('SELECT COUNT(*) FROM books')
        if c.fetchone()[0] == 0:
            seed = [
                # Original Lab 1 books
                (1, 'How to get a good grade in DOS in 40 minutes a day',
                 'distributed systems', 10, 30.0),
                (2, 'RPCs for Noobs',
                 'distributed systems', 10, 25.0),
                (3, 'Xen and the Art of Surviving Undergraduate School',
                 'undergraduate school', 10, 40.0),
                (4, 'Cooking for the Impatient Undergrad',
                 'undergraduate school', 10, 20.0),
                (5, 'How to finish Project 3 on time',
                 'distributed systems', 10, 35.0),
                (6, 'Why theory classes are so hard',
                 'undergraduate school', 10, 28.0),
                (7, 'Spring in the Pioneer Valley',
                 'undergraduate school', 10, 22.0),
            ]
            c.executemany(
                'INSERT INTO books (id, title, topic, quantity, price) VALUES (?, ?, ?, ?, ?)',
                seed
            )
            print('[CATALOG] Database seeded with 7 books.')
        conn.commit()
        conn.close()


# Cache invalidation & replica sync helpers

def invalidate_cache(item_id):
    """Push a cache invalidation to the front-end before a write (server-push consistency)."""
    if not FRONTEND_URL:
        return
    try:
        requests.post(f'{FRONTEND_URL}/invalidate/{item_id}', timeout=2)
        print(f'[CATALOG] Cache invalidation sent for item {item_id}')
    except Exception:
        pass  # best-effort; log in production, don't block the write


def sync_to_peer(item_id, data):
    """Replicate an update to the peer catalog replica after writing locally."""
    if not PEER_URL:
        return
    try:
        requests.put(
            f'{PEER_URL}/update/{item_id}',
            json={**data, '_sync': True},
            timeout=2
        )
        print(f'[CATALOG] Synced update for item {item_id} to peer {PEER_URL}')
    except Exception:
        pass  # in production this would retry with exponential backoff


# -------------------------------------------------------------------
# Endpoints
# -------------------------------------------------------------------

@app.route('/search/<path:topic>', methods=['GET'])
def search(topic):
    """
    Query books by topic/subject.
    Returns a JSON list of {id, title} objects for all matching books.
    Example: GET /search/distributed%20systems
    """
    with db_lock:
        conn = get_db()
        c = conn.cursor()
        c.execute('SELECT id, title FROM books WHERE topic = ?', (topic,))
        rows = c.fetchall()
        conn.close()

    result = [{'id': row['id'], 'title': row['title']} for row in rows]
    print(f'[CATALOG] search("{topic}") -> {len(result)} results')
    return jsonify(result), 200


@app.route('/info/<int:item_id>', methods=['GET'])
def info(item_id):
    """
    Query full details for a specific book by its item number.
    Returns {title, quantity, price} or 404 if not found.
    Example: GET /info/2
    """
    with db_lock:
        conn = get_db()
        c = conn.cursor()
        c.execute(
            'SELECT title, quantity, price FROM books WHERE id = ?',
            (item_id,)
        )
        row = c.fetchone()
        conn.close()

    if row is None:
        return jsonify({'error': f'Item {item_id} not found'}), 404

    result = {
        'title':    row['title'],
        'quantity': row['quantity'],
        'price':    row['price'],
    }
    print(f'[CATALOG] info({item_id}) -> {result}')
    return jsonify(result), 200


@app.route('/update/<int:item_id>', methods=['PUT'])
def update(item_id):
    """
    Update a book's price or adjust its stock quantity.
    Accepts a JSON body with optional fields:
      - "quantity": integer delta (e.g. -1 to decrement, +5 to restock)
      - "price":    new absolute price value
      - "_sync":    boolean flag — if True, this is a replica sync; skip
                    cache invalidation and peer forwarding to avoid loops.
    Example: PUT /update/2  {"quantity": -1}
    """
    data = request.get_json(force=True)
    if not data:
        return jsonify({'error': 'No JSON body provided'}), 400

    # Extract the internal sync flag (not stored in DB)
    is_sync = data.pop('_sync', False)

    with db_lock:
        conn = get_db()
        c = conn.cursor()

        c.execute('SELECT title FROM books WHERE id = ?', (item_id,))
        row = c.fetchone()
        if row is None:
            conn.close()
            return jsonify({'error': f'Item {item_id} not found'}), 404

        # Invalidate the front-end cache BEFORE writing (strong consistency guarantee).
        # Skip on sync writes — the primary replica already invalidated the cache.
        if not is_sync:
            invalidate_cache(item_id)

        if 'quantity' in data:
            c.execute(
                'UPDATE books SET quantity = quantity + ? WHERE id = ?',
                (data['quantity'], item_id)
            )

        if 'price' in data:
            c.execute(
                'UPDATE books SET price = ? WHERE id = ?',
                (data['price'], item_id)
            )

        conn.commit()
        conn.close()

    print(f'[CATALOG] update({item_id}) with {data} (sync={is_sync})')

    # Propagate the write to the peer replica (only for primary writes)
    if not is_sync:
        sync_to_peer(item_id, data)

    return jsonify({'success': True, 'message': f'Item {item_id} updated successfully'}), 200


if __name__ == '__main__':
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    init_db()
    app.run(host='0.0.0.0', port=5001, threaded=True)
