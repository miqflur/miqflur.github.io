"""
roblox_limited_items.py
=======================

This script fetches the most recent limited items created by the official
Roblox account.  A limited item on Roblox is an avatar accessory (such
as a hat, face or gear) that Roblox makes available only in limited
quantities.  Once all copies are sold, the item goes off sale and can
only be purchased from other users.  Each limited item has an `IsLimited`
or `IsLimitedUnique` flag set on its asset details.  Roblox maintains a
public catalogue API that can be queried to search for items and a
separate economy API that exposes detailed information for an individual
asset.  By combining these endpoints it is possible to assemble a list
of the latest limited items created by Roblox.

The script works in two phases:

1. **Catalog search** – It queries the marketplace search API
   (`https://catalog.roblox.com/v1/search/items/details`) for avatar
   items created by the user with ID 1 (the official "Roblox" account).
   The search results are paginated, so the script walks through pages
   until it collects at least the desired number of limited items.
   Limited items are identified by examining the `itemRestrictions`
   property returned in the search results; this list contains
   ``"Limited"`` or ``"LimitedUnique"`` for limited collectibles.

2. **Asset details** – For each candidate limited item the script
   fetches its details from the economy API (`https://economy.roblox.com/v2/assets/{assetId}/details`).
   This call returns creation and update timestamps along with flags
   indicating whether the item is limited and whether it is unique.
   The script uses these timestamps to sort the items in descending
   order of creation, converts them into the user’s local time zone,
   and assembles a structured record for presentation.

To avoid overwhelming the Roblox servers, the script respects HTTP
rate‑limit responses.  If the search or details request returns a
``429 Too Many Requests`` status, the script reads the ``Retry‑After``
header and waits for that many seconds before retrying.  This
simple back‑off strategy helps the script stay within the public API
limits.

Example usage::

    from roblox_limited_items import get_recent_limited_items

    items = get_recent_limited_items(num_items=25, timezone_str='America/Chicago')
    for i, item in enumerate(items, start=1):
        print(f"{i}. {item['name']} (ID: {item['id']})")
        print(f"   Created: {item['created_local']} | Updated: {item['updated_local']}")
        print(f"   Creator: {item['creator']} | Price: {item['price']} Robux | "
              f"LimitedUnique: {item['isLimitedUnique']} | Remaining: {item['remaining']}")

The default timezone, `America/Chicago`, matches the user’s locale.
If you wish to see times in a different zone, pass a valid IANA
timezone name via the ``timezone_str`` argument.

Note: This script communicates with Roblox’s public web APIs.  It may
fail if Roblox adjusts the endpoints or imposes additional
restrictions in the future.
"""

from __future__ import annotations

import time
from datetime import datetime
from typing import Dict, List, Optional
from zoneinfo import ZoneInfo

import requests


def _handle_rate_limiting(response: requests.Response) -> None:
    """Sleep according to the Retry‑After header if the response indicates rate limiting.

    Roblox’s API returns HTTP 429 when too many requests are made in a short
    period.  The ``Retry‑After`` header specifies how many seconds the
    client should wait before retrying.  This helper reads that header
    and sleeps for the appropriate amount of time.

    Args:
        response: The response object returned from ``requests``.
    """
    if response.status_code == 429:
        # default to 5 seconds if header is missing
        retry_after = 5
        try:
            retry_after = int(response.headers.get("Retry-After", "5"))
        except ValueError:
            pass
        time.sleep(retry_after)


def _fetch_catalog_page(session: requests.Session, params: Dict[str, str]) -> Dict:
    """Fetch a page of search results from the catalog API with basic rate‑limit handling.

    Args:
        session: A ``requests.Session`` used to persist connections and headers.
        params: Query parameters for the catalog search endpoint.

    Returns:
        The parsed JSON response as a dictionary.
    """
    url = "https://catalog.roblox.com/v1/search/items/details"
    while True:
        response = session.get(url, params=params)
        if response.status_code == 429:
            _handle_rate_limiting(response)
            continue
        response.raise_for_status()
        return response.json()


def _fetch_asset_details(session: requests.Session, asset_id: int) -> Optional[Dict]:
    """Fetch details for a specific asset from the economy API with basic rate‑limit handling.

    Args:
        session: A ``requests.Session`` used to persist connections and headers.
        asset_id: The numeric ID of the asset to fetch.

    Returns:
        A dictionary containing the asset details if successful, otherwise ``None``.
    """
    url = f"https://economy.roblox.com/v2/assets/{asset_id}/details"
    while True:
        response = session.get(url)
        if response.status_code == 429:
            _handle_rate_limiting(response)
            continue
        if response.status_code != 200:
            # abort on non-successful responses
            return None
        return response.json()


def get_recent_limited_items(num_items: int = 25, timezone_str: str = "America/Chicago") -> List[Dict[str, object]]:
    """Retrieve the most recently created limited items by the official Roblox account.

    This function walks through the Roblox catalog search pages until it
    gathers at least ``num_items`` limited items created by Roblox.  It then
    fetches detailed information for each item, sorts them by creation
    time in descending order, converts timestamps to the given time zone
    and returns the top ``num_items`` entries.

    Args:
        num_items: The number of limited items to return.  Defaults to 25.
        timezone_str: An IANA time zone name used to convert timestamps
            from UTC into local time.  Defaults to ``'America/Chicago'``.

    Returns:
        A list of dictionaries, each describing a limited item.  The keys
        include:

        - ``id``: the asset ID
        - ``name``: the item’s name
        - ``creator``: the creator’s name (should be ``'Roblox'``)
        - ``price``: the original sale price in Robux (may be ``None``)
        - ``created``: the raw ISO 8601 creation timestamp in UTC
        - ``updated``: the raw ISO 8601 updated timestamp in UTC
        - ``created_local``: the creation timestamp converted to the
          requested time zone and formatted for display
        - ``updated_local``: the updated timestamp converted to the
          requested time zone and formatted for display
        - ``isLimitedUnique``: ``True`` if the item is a limited unique
        - ``remaining``: number of copies remaining (may be ``None``)

    Note:
        The function may make several HTTP requests; network connectivity
        and Roblox API rate limits will affect execution time.
    """
    # Prepare a session with a generic User‑Agent to avoid being blocked.
    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": "Mozilla/5.0 (compatible; RobloxLimitedItemsScript/1.0)"
        }
    )

    # Query parameters for the catalog search.  Category=11 restricts
    # results to avatar items.  CreatorTargetId=1 and CreatorType='User'
    # ensure we only fetch items created by the official Roblox account.
    search_params: Dict[str, object] = {
        "Category": 11,
        "CreatorTargetId": 1,
        "CreatorType": "User",
        "Limit": 30,  # maximum allowed per page
        "SortType": 3,  # sort by updated time
        "SortAggregation": 5,  # consider all time
    }

    collected: List[Dict] = []
    next_cursor: Optional[str] = None
    # Fetch pages until we have enough candidate limited items.
    while len(collected) < num_items:
        if next_cursor:
            search_params["cursor"] = next_cursor
        elif "cursor" in search_params:
            search_params.pop("cursor")
        search_data = _fetch_catalog_page(session, search_params)
        for entry in search_data.get("data", []):
            restrictions = entry.get("itemRestrictions") or []
            if any(r in ("Limited", "LimitedUnique") for r in restrictions):
                collected.append(entry)
                if len(collected) >= num_items:
                    break
        next_cursor = search_data.get("nextPageCursor")
        if not next_cursor:
            # no more pages to fetch
            break

    # Fetch detailed info for each candidate limited item.
    detailed_items: List[Dict[str, object]] = []
    for entry in collected:
        details = _fetch_asset_details(session, entry["id"])
        if not details:
            continue
        if not (details.get("IsLimited") or details.get("IsLimitedUnique")):
            continue  # skip if not limited according to details API
        try:
            created_iso = details["Created"]
            updated_iso = details.get("Updated")
            created_dt = datetime.fromisoformat(created_iso.replace("Z", "+00:00"))
            updated_dt = None
            if updated_iso:
                updated_dt = datetime.fromisoformat(updated_iso.replace("Z", "+00:00"))
        except (TypeError, ValueError):
            # skip items with malformed timestamps
            continue
        detailed_items.append(
            {
                "id": details["AssetId"],
                "name": details["Name"],
                "creator": details.get("Creator", {}).get("Name"),
                "price": details.get("PriceInRobux"),
                "created": created_iso,
                "updated": updated_iso,
                "created_dt": created_dt,
                "updated_dt": updated_dt,
                "isLimitedUnique": details.get("IsLimitedUnique"),
                "remaining": details.get("Remaining"),
            }
        )

    # Sort by creation time descending
    detailed_items.sort(key=lambda x: x["created_dt"], reverse=True)

    # Convert times to requested timezone and format them for display
    tz = ZoneInfo(timezone_str)
    results: List[Dict[str, object]] = []
    for item in detailed_items[:num_items]:
        created_local_dt = item["created_dt"].astimezone(tz)
        updated_local_dt = (
            item["updated_dt"].astimezone(tz) if item["updated_dt"] is not None else None
        )
        results.append(
            {
                "id": item["id"],
                "name": item["name"],
                "creator": item["creator"],
                "price": item["price"],
                "created": item["created"],
                "updated": item["updated"],
                "created_local": created_local_dt.strftime("%Y-%m-%d %I:%M %p %Z"),
                "updated_local": updated_local_dt.strftime("%Y-%m-%d %I:%M %p %Z")
                if updated_local_dt
                else None,
                "isLimitedUnique": item["isLimitedUnique"],
                "remaining": item["remaining"],
            }
        )
    return results


def main() -> None:
    """Entry point for command line execution.

    Fetches and prints the 25 most recent limited items created by Roblox,
    displaying creation and update times in the user’s local time zone.
    """
    items = get_recent_limited_items(25, timezone_str="America/Chicago")
    for idx, item in enumerate(items, start=1):
        print(f"{idx}. {item['name']} (ID: {item['id']})")
        print(
            f"   Created: {item['created_local']} | Updated: {item['updated_local']}"
        )
        print(
            f"   Creator: {item['creator']} | Price: {item['price']} Robux | "
            f"LimitedUnique: {item['isLimitedUnique']} | Remaining: {item['remaining']}"
        )


if __name__ == "__main__":
    main()