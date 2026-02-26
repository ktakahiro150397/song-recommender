"""Utility script to hit the running FastAPI similarity endpoint.

Usage:
  uv run python tests/similar_probe.py --song "<song_id>" [--db full] [--n-results 10]
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any
from urllib.parse import quote

import httpx


def _pretty_print_response(resp: httpx.Response) -> None:
    """Print response status, headers of interest, and JSON (or raw text)."""
    request_id = resp.headers.get("x-request-id")
    server = resp.headers.get("server")
    duration = resp.headers.get("x-process-time")
    print(f"Status: {resp.status_code}")
    if request_id:
        print(f"Request-ID: {request_id}")
    if server:
        print(f"Server: {server}")
    if duration:
        print(f"Process-Time: {duration}")

    try:
        payload: Any = resp.json()
    except json.JSONDecodeError:
        print("--- response text ---")
        print(resp.text)
        return

    print("--- response json ---")
    print(json.dumps(payload, ensure_ascii=False, indent=2))


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Call the /api/songs/{id}/similar endpoint."
    )
    parser.add_argument(
        "--base-url",
        default="http://127.0.0.1:8001",
        help="FastAPI base URL (default: %(default)s)",
    )
    parser.add_argument(
        "--db",
        default="full",
        choices=("full", "balance", "minimal"),
        help="Vector DB name to query",
    )
    parser.add_argument(
        "--n-results",
        type=int,
        default=10,
        help="Number of similar songs to request",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=30.0,
        help="HTTP timeout in seconds",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Print request URL before sending",
    )
    parser.add_argument(
        "song_id",
        help="Song identifier key from song_metadata_db (include .wav suffix)",
    )
    args = parser.parse_args()

    base_url = args.base_url.rstrip("/")
    encoded_song_id = quote(args.song_id, safe="")
    url = f"{base_url}/api/songs/{encoded_song_id}/similar"
    params = {"db": args.db, "n_results": args.n_results}

    if args.verbose:
        print(f"GET {url}")
        print(f"Params: {params}")

    try:
        with httpx.Client(timeout=args.timeout) as client:
            response = client.get(url, params=params)
    except httpx.HTTPError as exc:
        print(f"HTTP request failed: {exc}")
        return 2

    _pretty_print_response(response)
    return 0 if response.status_code < 500 else 1


if __name__ == "__main__":
    raise SystemExit(main())
