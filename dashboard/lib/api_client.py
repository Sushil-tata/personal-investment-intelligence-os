import os
import requests

API_BASE = os.getenv("PIIOS_API_BASE", "http://127.0.0.1:8000/api/v1")


def get(path: str):
    response = requests.get(f"{API_BASE}{path}", timeout=20)
    response.raise_for_status()
    return response.json()
