import json
import subprocess
import time

import requests
from requests.exceptions import ConnectionError, HTTPError, ReadTimeout
from requests.models import Response


def is_valid_json(data):
    try:
        json.loads(data)
        return True
    except json.JSONDecodeError:
        return False


def nasdaq_headers():
    return {
        "authority": "api.nasdaq.com",
        "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
        "accept-language": "en-US,en;q=0.5",
        "cache-control": "max-age=0",
        "sec-ch-ua": '"Brave";v="113", "Chromium";v="113", "Not-A.Brand";v="24"',
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": '"macOS"',
        "sec-fetch-dest": "document",
        "sec-fetch-mode": "navigate",
        "sec-fetch-site": "none",
        "sec-fetch-user": "?1",
        "sec-gpc": "1",
        "upgrade-insecure-requests": "1",
        "user-agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/113.0.0.0 Safari/537.36",
    }


def yahoo_headers():
    return {
        "authority": "query1.finance.yahoo.com",
        "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
        "accept-language": "en-US,en;q=0.5",
        "cache-control": "max-age=0",
        "sec-ch-ua": '"Not/A)Brand";v="99", "Brave";v="115", "Chromium";v="115"',
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": '"macOS"',
        "sec-fetch-dest": "document",
        "sec-fetch-mode": "navigate",
        "sec-fetch-site": "none",
        "sec-fetch-user": "?1",
        "sec-gpc": "1",
        "upgrade-insecure-requests": "1",
        "user-agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36",
    }


def retry_get(
    url,
    headers={
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/106.0.0.0 Safari/537.36",
    },
    retries=10,
    delay=30,
    mode="default",
):
    if mode == "curl":
        curl_headers = []
        for k, v in headers.items():
            curl_headers += ["-H", f"{k}: {v}"]
        curl_command = [
            "curl",
            url,
            *curl_headers,
            "--compressed",
        ]
        for _ in range(retries):
            result = subprocess.run(curl_command, capture_output=True, text=True)
            content = result.stdout
            if result.returncode == 0 and is_valid_json(content):
                response = Response()
                response.status_code = 200
                response._content = content.encode("utf-8")
                return response
            else:
                print(f"Connection error with {url}. Retrying in {delay} seconds...")
                time.sleep(delay)
        raise ConnectionError(f"Failed to connect to {url} after {retries} retries")
    for _ in range(retries):
        try:
            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()  # Raise an exception for 4xx/5xx status codes
            return response
        except (ConnectionError, HTTPError, ReadTimeout):
            print(f"Connection error with {url}. Retrying in {delay} seconds...")
            time.sleep(delay)
    raise ConnectionError(f"Failed to connect to {url} after {retries} retries")


def send_sms(message: str):
    """
    Send a SMS using Twilio.
    """
    account_sid = os.environ["TWILIO_ACCOUNT_SID"]
    auth_token = os.environ["TWILIO_AUTH_TOKEN"]
    client = Client(account_sid, auth_token)
    client.messages.create(
        to=os.environ["TWILIO_TO"],
        from_=os.environ["TWILIO_FROM"],
        body=message,
    )
