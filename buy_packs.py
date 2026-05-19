"""
buy_packs.py — buy the daily 200-rax player pack for each player on the
auto-buy watchlist (watchlist_buy.json).

Real packs auto-deposit rating into the player's pass — there is no separate
"open" step. So a successful buy = +rating on the pass.

Confirmed flow (from ProxyPin capture, 2026-05-17):
  1. GET /collectingpacks/player?entityId=X&season=Y&sport=Z  (shop info, price)
  2. POST /collectingpacks/player   body shape:
       {
         "sport": "<mlb|nba|...>",
         "season": "<YYYY>",                # STRING
         "cost": <int>,                     # gate on this == 200
         "acceptPriceChanges": true,
         "entityId": "<player id>"          # STRING
       }

Safety:
  * dry-run by default; pass --live to actually post.
  * 4-8.5s jitter between any two outbound calls (set in client.py).
  * daily idempotency at state/bought_YYYY-MM-DD.json — won't buy twice.

Usage:
    python buy_packs.py                    # dry-run, prints what it WOULD do
    python buy_packs.py --live             # actually buy
    python buy_packs.py --account HDERDAR  # which env account (default HDERDAR)
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path

from accounts import get_account
from client import CADENCE_WRITE, RateLimitedClient

STATE_DIR = Path("state")
STATE_DIR.mkdir(exist_ok=True)
WATCHLIST_PATH = Path("watchlist_buy.json")
TARGET_PRICE_RAX = 200
DAILY_BUY_CAP_PER_PLAYER = 1   # one 200-rax pack per player per day


def state_path() -> Path:
    return STATE_DIR / f"bought_{date.today().isoformat()}.json"


def load_state() -> dict:
    p = state_path()
    if p.exists():
        return json.loads(p.read_text())
    return {"bought_entity_ids": []}


def save_state(state: dict) -> None:
    state_path().write_text(json.dumps(state, indent=2))


def load_watchlist() -> list[dict]:
    if not WATCHLIST_PATH.exists():
        print(f"[X] missing {WATCHLIST_PATH}")
        sys.exit(2)
    items = json.loads(WATCHLIST_PATH.read_text())
    return [it for it in items if it.get("enabled", True)]


def get_pack_shop_info(client: RateLimitedClient, entry: dict) -> dict | None:
    """Returns the shop-info JSON for this player's daily pack, or None."""
    resp = client.get(
        "/collectingpacks/player",
        params={
            "entityId": entry["entityId"],
            "season": entry["season"],
            "sport": entry["sport"],
        },
    )
    if resp.status_code != 200:
        print(f"  [!] shop info failed: {resp.status_code} {resp.text[:200]}")
        return None
    return resp.json()


def buy_pack(client: RateLimitedClient, entry: dict, shop_info: dict, state: dict) -> bool:
    label = entry["label"]
    entity_id = entry["entityId"]

    # Shop info shape (confirmed 2026-05-17):
    #   { "info": { "cost": <int>, "isCostDynamic": false,
    #               "purchaseDisabledMessage": "...", ... } }
    info = shop_info.get("info") or shop_info
    cost = info.get("cost")
    if not isinstance(cost, (int, float)):
        print(f"  [!] couldn't find info.cost in shop info; keys: {list(shop_info.keys())}")
        return False
    cost = int(cost)

    # The API surfaces a soft block when no packs remain for the day; this
    # message is the readable signal that today's 200-rax window is used up.
    disabled_msg = info.get("purchaseDisabledMessage")

    if cost != TARGET_PRICE_RAX:
        if disabled_msg:
            print(f"  [ ] {label}: price={cost} rax (today's window used — '{disabled_msg}')")
        else:
            print(f"  [ ] {label}: price={cost} rax ≠ {TARGET_PRICE_RAX}; skip")
        return False

    # Body shape — exact match to the captured POST.
    body = {
        "sport": entry["sport"],
        "season": str(entry["season"]),
        "cost": cost,
        "acceptPriceChanges": True,
        "entityId": str(entity_id),
    }
    resp = client.post("/collectingpacks/player", json_body=body, confirm_write=True)
    if resp.status_code != 200:
        print(f"  [!] {label}: buy failed: {resp.status_code} {resp.text[:300]}")
        return False
    print(f"  [+] {label}: bought 1× pack for {cost} rax (entity {entity_id})")
    state["bought_entity_ids"].append(entity_id)
    save_state(state)
    return True


def run_for_entry(client: RateLimitedClient, entry: dict, state: dict) -> bool:
    label = entry["label"]
    entity_id = entry["entityId"]

    if state["bought_entity_ids"].count(entity_id) >= DAILY_BUY_CAP_PER_PLAYER:
        print(f"[ ] {label}: already bought today; skip")
        return False
    print(f"[?] {label} (entity {entity_id}, {entry['sport']} {entry['season']})")
    shop_info = get_pack_shop_info(client, entry)
    if shop_info is None:
        return False
    return buy_pack(client, entry, shop_info, state)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--account", default="HDERDAR")
    parser.add_argument("--live", action="store_true",
                        help="actually buy (default: dry-run)")
    args = parser.parse_args()

    fp = get_account(args.account)
    min_gap, max_gap = CADENCE_WRITE
    client = RateLimitedClient(fp, min_gap_s=min_gap, max_gap_s=max_gap, dry_run=not args.live)
    state = load_state()
    watchlist = load_watchlist()
    print(f"[i] account={args.account}  live={args.live}  watchlist={len(watchlist)} player(s)")

    n_bought = 0
    for entry in watchlist:
        if run_for_entry(client, entry, state):
            n_bought += 1
    print(f"\n[i] done — bought {n_bought} pack(s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
