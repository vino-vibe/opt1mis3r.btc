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
    python buy_packs.py --account HDERDAR  # single account (default HDERDAR)
    python buy_packs.py --all-accounts --live  # all accounts in ACCOUNTS env var
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path

from accounts import get_account, get_all_accounts
from client import CADENCE_WRITE, RateLimitedClient

STATE_DIR = Path("state")
STATE_DIR.mkdir(exist_ok=True)
WATCHLIST_PATH = Path("watchlist_buy.json")
TARGET_PRICE_RAX = 200
DAILY_BUY_CAP_PER_PLAYER = 1   # one 200-rax pack per player per day


def state_path(account_name: str) -> Path:
    return STATE_DIR / f"bought_{account_name}_{date.today().isoformat()}.json"


def load_state(account_name: str) -> dict:
    p = state_path(account_name)
    if p.exists():
        return json.loads(p.read_text())
    return {"bought_entity_ids": []}


def save_state(account_name: str, state: dict) -> None:
    state_path(account_name).write_text(json.dumps(state, indent=2))


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


def buy_pack(client: RateLimitedClient, account_name: str, entry: dict, shop_info: dict, state: dict) -> bool:
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
    save_state(account_name, state)
    return True


def run_for_entry(client: RateLimitedClient, account_name: str, entry: dict, state: dict) -> bool:
    label = entry["label"]
    entity_id = entry["entityId"]

    if state["bought_entity_ids"].count(entity_id) >= DAILY_BUY_CAP_PER_PLAYER:
        print(f"[ ] {label}: already bought today; skip")
        return False
    print(f"[?] {label} (entity {entity_id}, {entry['sport']} {entry['season']})")
    shop_info = get_pack_shop_info(client, entry)
    if shop_info is None:
        return False
    return buy_pack(client, account_name, entry, shop_info, state)


def run_account(fp, watchlist: list[dict], live: bool) -> int:
    min_gap, max_gap = CADENCE_WRITE
    client = RateLimitedClient(fp, min_gap_s=min_gap, max_gap_s=max_gap, dry_run=not live)
    state = load_state(fp.name)
    print(f"\n{'='*60}")
    print(f"[i] account={fp.name}  live={live}  watchlist={len(watchlist)} player(s)")
    print(f"{'='*60}")
    n_bought = 0
    for entry in watchlist:
        if run_for_entry(client, fp.name, entry, state):
            n_bought += 1
    print(f"\n[i] {fp.name} done — bought {n_bought} pack(s)")
    return n_bought


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    grp = parser.add_mutually_exclusive_group()
    grp.add_argument("--account", default=None,
                     help="single named account (default: HDERDAR)")
    grp.add_argument("--all-accounts", action="store_true",
                     help="loop every account declared in ACCOUNTS")
    parser.add_argument("--live", action="store_true",
                        help="actually buy (default: dry-run)")
    args = parser.parse_args()

    if args.all_accounts:
        fps = get_all_accounts()
    else:
        fps = [get_account(args.account or "HDERDAR")]

    watchlist = load_watchlist()
    total = 0
    for fp in fps:
        total += run_account(fp, watchlist, args.live)

    print(f"\n[i] grand total — {total} pack(s) across {len(fps)} account(s)")
    return 0


def _buy_packs_entry_gen(client, account_name, entry, state):
    """Sub-generator: yields log lines, returns True if pack was bought."""
    label = entry["label"]
    entity_id = entry["entityId"]

    if state["bought_entity_ids"].count(entity_id) >= DAILY_BUY_CAP_PER_PLAYER:
        yield f"[ ] {label}: already bought today; skip"
        return False

    yield f"[?] {label} (entity {entity_id}, {entry['sport']} {entry['season']})"

    resp = client.get("/collectingpacks/player", params={
        "entityId": entry["entityId"],
        "season": entry["season"],
        "sport": entry["sport"],
    })
    if resp.status_code != 200:
        yield f"  [!] shop info failed: {resp.status_code} {resp.text[:200]}"
        return False
    shop_info = resp.json()

    info = shop_info.get("info") or shop_info
    cost = info.get("cost")
    if not isinstance(cost, (int, float)):
        yield f"  [!] couldn't find info.cost in shop info; keys: {list(shop_info.keys())}"
        return False
    cost = int(cost)
    disabled_msg = info.get("purchaseDisabledMessage")

    if cost != TARGET_PRICE_RAX:
        if disabled_msg:
            yield f"  [ ] {label}: price={cost} rax (today's window used — '{disabled_msg}')"
        else:
            yield f"  [ ] {label}: price={cost} rax ≠ {TARGET_PRICE_RAX}; skip"
        return False

    body = {
        "sport": entry["sport"],
        "season": str(entry["season"]),
        "cost": cost,
        "acceptPriceChanges": True,
        "entityId": str(entity_id),
    }
    resp = client.post("/collectingpacks/player", json_body=body, confirm_write=True)
    if resp.status_code != 200:
        yield f"  [!] {label}: buy failed: {resp.status_code} {resp.text[:300]}"
        return False

    yield f"  [+] {label}: bought 1× pack for {cost} rax (entity {entity_id})"
    state["bought_entity_ids"].append(entity_id)
    save_state(account_name, state)
    return True


def run(account=None, all_accounts=False, live=False):
    """Generator version — yields log lines instead of printing."""
    if all_accounts:
        fps = get_all_accounts()
    else:
        fps = [get_account(account or "HDERDAR")]

    if not WATCHLIST_PATH.exists():
        yield f"[X] missing {WATCHLIST_PATH}"
        return
    items = json.loads(WATCHLIST_PATH.read_text())
    watchlist = [it for it in items if it.get("enabled", True)]

    min_gap, max_gap = CADENCE_WRITE
    grand_total = 0
    for fp in fps:
        client = RateLimitedClient(fp, min_gap_s=min_gap, max_gap_s=max_gap, dry_run=not live)
        state = load_state(fp.name)
        yield f"\n{'='*60}"
        yield f"[i] account={fp.name}  live={live}  watchlist={len(watchlist)} player(s)"
        yield f"{'='*60}"
        n_bought = 0
        for entry in watchlist:
            bought = yield from _buy_packs_entry_gen(client, fp.name, entry, state)
            if bought:
                n_bought += 1
        yield f"\n[i] {fp.name} done — bought {n_bought} pack(s)"
        grand_total += n_bought
    yield f"\n[i] grand total — {grand_total} pack(s) across {len(fps)} account(s)"


if __name__ == "__main__":
    sys.exit(main())
