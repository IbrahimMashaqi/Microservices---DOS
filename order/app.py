"""
Bazar.com - Order Server
Handles book purchases. Verifies stock with the Catalog Server,
decrements stock on success, and logs orders to SQLite.
Runs on port 5002.
"""

import os
import sqlite3
import threading
from datetime import datetime, timezone

import requests
from flask import Flask, jsonify

app = Flask(__name__)

# Location of the SQLite order log database
DB_PATH = os.path.join(os.path.dirname(__file__), 'orders.db')

# Thread-safety lock for SQLite writes
db_lock = threading.Lock()

# Catalog service base URL — overridable via environment variable
CATALOG_URL = os.environ.get('CATALOG_URL', 'http://catalog:5001')


def get_db():
    """Open a new database connection."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Create the orders table if it doesn't exist yet."""
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


# -------------------------------------------------------------------
# Endpoints
# -------------------------------------------------------------------

@app.route('/purchase/<int:item_id>', methods=['POST'])
def purchase(item_id):
    """
    Purchase a book by item ID.
    Steps:
      1. Query the Catalog Server to check availability.
      2. If in stock, send a PUT /update request to decrement stock by 1.
      3. Log the successful order to the local SQLite database.
      4. Return success message or appropriate error.
    Example: POST /purchase/2
    """
    # Step 1 — Check stock with catalog server
    try:
        catalog_resp = requests.get(f'{CATALOG_URL}/info/{item_id}', timeout=5)
    except requests.exceptions.ConnectionError:
        return jsonify({'error': 'Catalog service is unavailable'}), 503

    if catalog_resp.status_code == 404:
        print(f'[ORDER] Purchase failed: item {item_id} not found in catalog.')
        return jsonify({'success': False, 'error': f'Item {item_id} not found'}), 404

    book_info = catalog_resp.json()

    # Step 2 — Check if out of stock
    if book_info.get('quantity', 0) <= 0:
        print(f'[ORDER] Purchase failed: "{book_info["title"]}" is out of stock.')
        return jsonify({
            'success': False,
            'error': f'"{book_info["title"]}" is out of stock'
        }), 400

    # Step 3 — Decrement stock in catalog
    try:
        update_resp = requests.put(
            f'{CATALOG_URL}/update/{item_id}',
            json={'quantity': -1},
            timeout=5
        )
        if update_resp.status_code != 200:
            return jsonify({'error': 'Failed to update catalog stock'}), 500
    except requests.exceptions.ConnectionError:
        return jsonify({'error': 'Catalog service is unavailable'}), 503

    # Step 4 — Log order to local database
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

    print(f'[ORDER] bought book "{book_info["title"]}"')
    return jsonify({
        'success': True,
        'message': f'bought book {book_info["title"]}'
    }), 200


if __name__ == '__main__':
    init_db()
    app.run(host='0.0.0.0', port=5002, threaded=True)
