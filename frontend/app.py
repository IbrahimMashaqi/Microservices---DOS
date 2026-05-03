"""
Bazar.com - Front-End Server
Single entry point for all client requests. Routes:
  - search / info  -> Catalog Server
  - purchase       -> Order Server
Runs on port 5000.
"""

import os
import requests
from flask import Flask, jsonify

app = Flask(__name__)

# Backend service URLs — configurable via environment variables for Docker
CATALOG_URL = os.environ.get('CATALOG_URL', 'http://catalog:5001')
ORDER_URL   = os.environ.get('ORDER_URL',   'http://order:5002')


# -------------------------------------------------------------------
# Helper
# -------------------------------------------------------------------

def _proxy_get(url):
    """Issue a GET request to a backend service and return its JSON response."""
    try:
        resp = requests.get(url, timeout=5)
        return jsonify(resp.json()), resp.status_code
    except requests.exceptions.ConnectionError as e:
        return jsonify({'error': f'Backend unavailable: {e}'}), 503


def _proxy_post(url):
    """Issue a POST request to a backend service and return its JSON response."""
    try:
        resp = requests.post(url, timeout=5)
        return jsonify(resp.json()), resp.status_code
    except requests.exceptions.ConnectionError as e:
        return jsonify({'error': f'Backend unavailable: {e}'}), 503


# -------------------------------------------------------------------
# Client-facing Endpoints
# -------------------------------------------------------------------

@app.route('/search/<path:topic>', methods=['GET'])
def search(topic):
    """
    Search books by topic. Proxied to the Catalog Server.
    Example: GET /search/distributed%20systems
    Returns a list of {id, title} objects.
    """
    print(f'[FRONTEND] search("{topic}") -> catalog')
    return _proxy_get(f'{CATALOG_URL}/search/{topic}')


@app.route('/info/<int:item_id>', methods=['GET'])
def info(item_id):
    """
    Get full details for a book by item number. Proxied to the Catalog Server.
    Example: GET /info/2
    Returns {title, quantity, price}.
    """
    print(f'[FRONTEND] info({item_id}) -> catalog')
    return _proxy_get(f'{CATALOG_URL}/info/{item_id}')


@app.route('/purchase/<int:item_id>', methods=['POST'])
def purchase(item_id):
    """
    Purchase a book by item number. Proxied to the Order Server.
    Example: POST /purchase/2
    Returns success/failure message.
    """
    print(f'[FRONTEND] purchase({item_id}) -> order')
    return _proxy_post(f'{ORDER_URL}/purchase/{item_id}')


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, threaded=True)
