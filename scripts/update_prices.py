#!/usr/bin/env python3
"""Fetch HorizonXI currency prices (both AH and Bazaar) from PSXI and write prices.json."""

from datetime import datetime, timezone
from pathlib import Path
import re
import json
import sys
import time
import statistics

import requests
from bs4 import BeautifulSoup

BASE = "https://www.psxi.gg/s/horizonxi/ah/misc-3/"
URLS = {
    "byne": BASE + "1-byne-bill",
    "whiteshell": BASE + "t-whiteshell",
    "bronzepiece": BASE + "o-bronzepiece",
}

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/131.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}


def get_soup(session, url):
    response = session.get(url, headers=HEADERS, timeout=30)
    response.raise_for_status()
    return BeautifulSoup(response.text, "html.parser")


def parse_ah_data(soup):
    text = soup.get_text(" ", strip=True)
    match = re.search(
        r"Single\s+([\d,]+)\s*gil\s+Avg\s+([\d,]+)\s+Median\s+([\d,]+)\s+Stock\s+([\d,]+)",
        text,
        re.IGNORECASE,
    )
    if not match:
        return None

    values = [int(value.replace(",", "")) for value in match.groups()]
    return {
        "single": values[0],
        "average": values[1],
        "median": values[2],
        "stock": values[3],
    }


def parse_bazaar_data(soup):
    heading = None
    for element in soup.find_all(["h2", "h3", "h4"]):
        if "Bazaar Listings" in element.get_text(" ", strip=True):
            heading = element
            break

    if heading is None:
        return None

    table = heading.find_next("table")
    if table is None:
        return None

    prices = []
    for row in table.find_all("tr"):
        cells = [cell.get_text(" ", strip=True) for cell in row.find_all(["td"])]
        if len(cells) < 2:
            continue

        # Parse price column without filtering out offline players
        price_match = re.search(r"([\d,]+)", cells[1])
        if not price_match:
            continue
        price = int(price_match.group(1).replace(",", ""))
        if price > 0:
            prices.append(price)

    if not prices:
        return None

    prices.sort()
    return {
        "lowest": prices[0],
        "median": int(statistics.median(prices)),
        "listings": len(prices),
    }


def parse_item_data(soup):
    return {
        "ah": parse_ah_data(soup),
        "bazaar": parse_bazaar_data(soup),
    }


def main():
    items = [
        ("byne", "1 Byne Bill"),
        ("whiteshell", "T. Whiteshell"),
        ("bronzepiece", "O. Bronzepiece"),
    ]

    data = {
        "updated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "server": "HorizonXI",
        "provider": "PSXI",
        "source_urls": URLS,
    }

    with requests.Session() as session:
        for index, (key, name) in enumerate(items):
            if index > 0:
                time.sleep(2)
            soup = get_soup(session, URLS[key])
            data[key] = parse_item_data(soup)

    output = Path("prices.json")
    output.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {output}")
    print(json.dumps(data, indent=2))


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"Price update failed: {exc}", file=sys.stderr)
        raise