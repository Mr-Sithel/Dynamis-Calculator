#!/usr/bin/env python3
"""Fetch HorizonXI currency prices from PSXI and write prices.json."""

from datetime import datetime, timezone
from pathlib import Path
import re
import json
import sys
import time

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


def get_soup(session, url, retries=3):
    for attempt in range(1, retries + 1):
        response = session.get(url, headers=HEADERS, timeout=30)
        if response.status_code == 429:
            retry_after = int(response.headers.get("Retry-After", 15 * attempt))
            print(f"Rate limited (429) on {url}. Waiting {retry_after}s before retry {attempt}/{retries}...")
            time.sleep(retry_after)
            continue
        response.raise_for_status()
        return BeautifulSoup(response.text, "html.parser")

    response.raise_for_status()


def parse_ah_single(soup, item_name):
    # PSXI presents the item summary in this order:
    # Single <price> gil Avg <average> Median <median> Stock <stock>
    text = soup.get_text(" ", strip=True)
    match = re.search(
        r"Single\s+([\d,]+)\s*gil\s+Avg\s+([\d,]+)\s+Median\s+([\d,]+)\s+Stock\s+([\d,]+)",
        text,
        re.IGNORECASE,
    )
    if not match:
        raise ValueError(f"Could not find the AH single-price summary for {item_name}")

    values = [int(value.replace(",", "")) for value in match.groups()]
    
    # If stock and single price are both 0, treat it as unavailable data to trigger fallback
    if values[0] == 0 and values[3] == 0:
        raise ValueError(f"AH summary for {item_name} has zero price and stock")

    return {
        "single": values[0],
        "average": values[1],
        "median": values[2],
        "stock": values[3],
        "source": "Auction House single-item summary",
    }


def parse_lowest_online_bazaar(soup, item_name):
    # Find the Bazaar Listings heading, then inspect its first table.
    heading = None
    for element in soup.find_all(["h2", "h3", "h4"]):
        if "Bazaar Listings" in element.get_text(" ", strip=True):
            heading = element
            break

    if heading is None:
        raise ValueError(f"Could not find the Bazaar Listings section for {item_name}")

    table = heading.find_next("table")
    if table is None:
        raise ValueError(f"Could not find the Bazaar listings table for {item_name}")

    listings = []
    for row in table.find_all("tr"):
        cells = [cell.get_text(" ", strip=True) for cell in row.find_all(["td", "th"])]
        if len(cells) < 4:
            continue

        row_text = " ".join(cells)
        if not re.search(r"\bOnline\b", row_text, re.IGNORECASE):
            continue

        # PSXI's listing table columns are Seller, Price, Qty, Zone, Status.
        price_match = re.search(r"([\d,]+)", cells[1])
        if not price_match:
            continue
        price = int(price_match.group(1).replace(",", ""))

        quantity_match = re.search(r"\d+", cells[2])
        quantity = int(quantity_match.group()) if quantity_match else None
        listings.append((price, quantity))

    if not listings:
        raise ValueError(f"No active online Bazaar listings were found for {item_name}")

    lowest_price, quantity = min(listings, key=lambda item: item[0])
    return {
        "lowest_bazaar": lowest_price,
        "quantity": quantity,
        "source": "Lowest active online Bazaar asking price (not an AH sale)",
    }


def parse_item_data(soup, item_name):
    """
    1. Check Auction House first.
    2. If no AH price/stock is available, fall back to lowest online Bazaar price.
    """
    try:
        return parse_ah_single(soup, item_name)
    except (ValueError, AttributeError) as ah_error:
        try:
            return parse_lowest_online_bazaar(soup, item_name)
        except (ValueError, AttributeError) as bazaar_error:
            raise ValueError(
                f"Failed to retrieve pricing for {item_name}. "
                f"AH Error: {ah_error} | Bazaar Error: {bazaar_error}"
            )


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
                time.sleep(3)  # Brief pause between requests to avoid triggering rate limits
            soup = get_soup(session, URLS[key])
            data[key] = parse_item_data(soup, name)

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