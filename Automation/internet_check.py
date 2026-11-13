import requests #pip install requests


def is_Online(url="https://www.google.com", timeout=3):
    try:
        response = requests.get(url, timeout=timeout)
        return 200 <= response.status_code < 300
    except (requests.RequestException, OSError):
        return False
