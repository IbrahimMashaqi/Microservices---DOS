"""
Bazar.com - Catalog Server
Manages the book catalog: search by topic, info by item ID, and stock/price updates.
Runs on port 5001.
"""

import os
import sqlite3
import threading
from flask import Flask, jsonify, request

app = Flask(__name__)

# Path to SQLite database file
DB_PATH = os.path.join(os.path.dirname(__file__), 'catalog.db')

# Lock to make SQLite writes thread-safe under concurrent requests
db_lock = threading.Lock()


def get_db():
    """Open a new database connection (SQLite is not thread-safe for sharing)."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row  # allows dict-style row access
    return conn


def init_db():
    """Create the books table and seed it with the four initial books."""
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
        # Only insert seed data if the table is empty
        c.execute('SELECT COUNT(*) FROM books')
        if c.fetchone()[0] == 0:
            seed = [
                (1, 'How to get a good grade in DOS in 40 minutes a day',
                 'distributed systems', 10, 30.0),
                (2, 'RPCs for Noobs',
                 'distributed systems', 10, 25.0),
                (3, 'Xen and the Art of Surviving Undergraduate School',
                 'undergraduate school', 10, 40.0),
                (4, 'Cooking for the Impatient Undergrad',
                 'undergraduate school', 10, 20.0),
            ]
            c.executemany(
                'INSERT INTO books (id, title, topic, quantity, price) VALUES (?, ?, ?, ?, ?)',
                seed
            )
            print('[CATALOG] Database seeded with 4 books.')
        conn.commit()
        conn.close()


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
    Example: PUT /update/2  {"quantity": -1}
    """
    data = request.get_json(force=True)
    if not data:
        return jsonify({'error': 'No JSON body provided'}), 400

    with db_lock:
        conn = get_db()
        c = conn.cursor()

        # Confirm the item exists
        c.execute('SELECT title FROM books WHERE id = ?', (item_id,))
        row = c.fetchone()
        if row is None:
            conn.close()
            return jsonify({'error': f'Item {item_id} not found'}), 404

        # Apply quantity delta if provided
        if 'quantity' in data:
            c.execute(
                'UPDATE books SET quantity = quantity + ? WHERE id = ?',
                (data['quantity'], item_id)
            )

        # Apply new price if provided
        if 'price' in data:
            c.execute(
                'UPDATE books SET price = ? WHERE id = ?',
                (data['price'], item_id)
            )

        conn.commit()
        conn.close()

    print(f'[CATALOG] update({item_id}) with {data}')
    return jsonify({'success': True, 'message': f'Item {item_id} updated successfully'}), 200


if __name__ == '__main__':
    init_db()
    # threaded=True lets Flask handle concurrent requests via multiple threads
    app.run(host='0.0.0.0', port=5001, threaded=True)
