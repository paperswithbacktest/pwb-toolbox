import time

import requests
from requests.exceptions import ConnectionError, HTTPError, ReadTimeout


def retry_get(
    url,
    headers={
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/106.0.0.0 Safari/537.36",
    },
    retries=10,
    delay=300,
):
    for _ in range(retries):
        try:
            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()  # Raise an exception for 4xx/5xx status codes
            return response
        except (ConnectionError, HTTPError, ReadTimeout):
            print(f"Connection error with {url}. Retrying in {delay} seconds...")
            time.sleep(delay)
    raise ConnectionError(f"Failed to connect to {url} after {retries} retries")
