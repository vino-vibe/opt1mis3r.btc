"""
list_pass.py — list watchlisted player passes on the Real marketplace.

For each pass on watchlist_list.json:
  1. GET /userpasses/{cardId}        → current rating
  2. If rating < 80 (rare threshold) → skip
  3. Fetch meowbot recommended price for (entityId, season) at RARE
  4. minBidPrice = round_down_tick(meowbot * 0.90)
     buyNowPrice = round_up_tick(meowbot * 1.10)
  5. POST /cardmarketplacelistings with the captured body shape
  6. Mark the cardId as listed in state/listed_YYYY-MM-DD.json (idempotent)

Posture: dry-run by default. --live actually mutates. Refuses to run if any
required field is missing.

Usage:
    python list_pass.py                  # dry-run, prints intended listings
    python list_pass.py --live           # actually post to marketplace
    python list_pass.py --account HDERDAR
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path

from accounts import get_account
from client import CADENCE_WRITE, RateLimitedClient
from meowbot import RARITY_RARE, recommended_price_for_pass
from pricing import round_down_tick, round_up_tick

STATE_DIR = Path("state")
STATE_DIR.mkdir(exist_ok=True)
WATCHLIST_PATH = Path("watchlist_list.json")

# Rarity threshold for listing — see Project_vision.md
RARE_RATING_THRESHOLD = 80.0

# Pricing multipliers per project spec (90% bid / 110% buy-now)
BID_MULTIPLIER = 0.90
BUY_NOW_MULTIPLIER = 1.10

# Listing duration in hours — value confirmed from captured POST body.
# (Spec mentioned "10 minute auction" — unresolved discrepancy; using captured value.)
LISTING_DURATION_HOURS = 72


def state_path() -> Path:
    return STATE_DIR / f"listed_{date.today().isoformat()}.json"


def load_state() -> dict:
    p = state_path()
    if p.exists():
        return json.loads(p.read_text())
    return {"listed_card_ids": []}


def save_state(state: dict) -> None:
    state_path().write_text(json.dumps(state, indent=2))


def load_watchlist() -> list[dict]:
    if not WATCHLIST_PATH.exists():
        print(f"[X] missing {WATCHLIST_PATH}")
        sys.exit(2)
    items = json.loads(WATCHLIST_PATH.read_text())
    return [it for it in items if it.get("enabled", True)]


def get_pass_state(client: RateLimitedClient, card_id: int) -> tuple[float, int] | None:
    """
    GET /userpasses/{cardId} → (rating, baseRarity) or None on failure.

    Response shape (confirmed from Ohtani 2026 capture):
      data.pass.boostValue       — stringified float rating, e.g. "80.7"
      data.pass.boostInfo.baseRarity — int (3=Rare, 4=Epic, 5=Legendary, ...)
    """
    resp = client.get(f"/userpasses/{card_id}")
    if resp.status_code != 200:
        print(f"  [!] fetch pass {card_id} failed: {resp.status_code} {resp.text[:200]}")
        return None
    payload = resp.json()
    pass_obj = payload.get("pass") or {}
    boost_value = pass_obj.get("boostValue")
    base_rarity = (pass_obj.get("boostInfo") or {}).get("baseRarity")
    if boost_value is None or base_rarity is None:
        print(f"  [!] pass {card_id} response missing boostValue/baseRarity; "
              f"pass keys: {list(pass_obj.keys())[:10]}")
        return None
    try:
        return float(boost_value), int(base_rarity)
    except (TypeError, ValueError) as e:
        print(f"  [!] pass {card_id} couldn't parse rating/rarity: {e}")
        return None


def build_listing_body(card_id: int, min_bid: int, buy_now: int) -> dict:
    """Exact shape from your captured POST /cardmarketplacelistings."""
    return {
        "listingType": "userpassfull",
        "cardId": card_id,
        "minBidPrice": min_bid,
        "allowBids": True,
        "buyNowPrice": buy_now,
        "durationInHours": LISTING_DURATION_HOURS,
        "notificationSettings": {"notifyeverybid": False, "notifytenmin": False},
    }


def list_pass(
    client: RateLimitedClient, entry: dict, state: dict
) -> bool:
    label = entry["label"]
    card_id = entry["cardId"]
    entity_id = entry["entityId"]
    season = entry["season"]

    if card_id in state["listed_card_ids"]:
        print(f"[ ] {label} (card {card_id}): already listed today; skip")
        return False

    print(f"[?] {label} (card {card_id}, entity {entity_id})")

    # 1. Current rating + rarity (from API source of truth)
    state_pair = get_pass_state(client, card_id)
    if state_pair is None:
        return False
    rating, base_rarity = state_pair
    if base_rarity < RARITY_RARE:
        print(f"    rating={rating:.1f} baseRarity={base_rarity} (<Rare={RARITY_RARE}) — skip")
        return False

    # 2. Meowbot recommended price — use the pass's actual rarity, not just RARE
    try:
        rec = recommended_price_for_pass(entity_id, season, rating, rarity=base_rarity)
    except Exception as e:
        print(f"    [!] meowbot fetch failed: {e}")
        return False
    if rec is None:
        print(f"    [!] meowbot returned no price (sample size too low); skip")
        return False

    # 3. Round to valid ticks
    min_bid = round_down_tick(rec * BID_MULTIPLIER)
    buy_now = round_up_tick(rec * BUY_NOW_MULTIPLIER)
    if min_bid >= buy_now:
        print(f"    [!] derived prices collapse: bid={min_bid} buyNow={buy_now}; skip")
        return False
    print(f"    rating={rating:.1f}  meowbot≈{rec:.0f}  →  bid={min_bid}  buyNow={buy_now}")

    # 4. POST listing
    body = build_listing_body(card_id, min_bid, buy_now)
    resp = client.post("/cardmarketplacelistings", json_body=body, confirm_write=True)
    if resp.status_code != 200:
        print(f"    [!] list failed: {resp.status_code} {resp.text[:300]}")
        return False
    print(f"    [+] listed")
    state["listed_card_ids"].append(card_id)
    save_state(state)
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--account", default="HDERDAR")
    parser.add_argument("--live", action="store_true",
                        help="actually post listings (default: dry-run)")
    args = parser.parse_args()

    fp = get_account(args.account)
    min_gap, max_gap = CADENCE_WRITE
    client = RateLimitedClient(fp, min_gap_s=min_gap, max_gap_s=max_gap, dry_run=not args.live)
    state = load_state()

    watchlist = load_watchlist()
    print(f"[i] account={args.account}  live={args.live}  watchlist={len(watchlist)} pass(es)")

    n_listed = 0
    for entry in watchlist:
        if list_pass(client, entry, state):
            n_listed += 1

    print(f"\n[i] done — listed {n_listed} pass(es)")
    return 0


def _list_pass_entry_gen(client, entry, state):
    """Sub-generator: yields log lines, returns True if pass was listed."""
    label = entry["label"]
    card_id = entry["cardId"]
    entity_id = entry["entityId"]
    season = entry["season"]

    if card_id in state["listed_card_ids"]:
        yield f"[ ] {label} (card {card_id}): already listed today; skip"
        return False

    yield f"[?] {label} (card {card_id}, entity {entity_id})"

    resp = client.get(f"/userpasses/{card_id}")
    if resp.status_code != 200:
        yield f"  [!] fetch pass {card_id} failed: {resp.status_code} {resp.text[:200]}"
        return False
    payload = resp.json()
    pass_obj = payload.get("pass") or {}
    boost_value = pass_obj.get("boostValue")
    base_rarity = (pass_obj.get("boostInfo") or {}).get("baseRarity")
    if boost_value is None or base_rarity is None:
        yield f"  [!] pass {card_id} response missing boostValue/baseRarity"
        return False
    try:
        rating = float(boost_value)
        base_rarity = int(base_rarity)
    except (TypeError, ValueError) as e:
        yield f"  [!] pass {card_id} couldn't parse rating/rarity: {e}"
        return False

    if base_rarity < RARITY_RARE:
        yield f"    rating={rating:.1f} baseRarity={base_rarity} (<Rare={RARITY_RARE}) — skip"
        return False

    try:
        rec = recommended_price_for_pass(entity_id, season, rating, rarity=base_rarity)
    except Exception as e:
        yield f"    [!] meowbot fetch failed: {e}"
        return False
    if rec is None:
        yield f"    [!] meowbot returned no price (sample size too low); skip"
        return False

    min_bid = round_down_tick(rec * BID_MULTIPLIER)
    buy_now = round_up_tick(rec * BUY_NOW_MULTIPLIER)
    if min_bid >= buy_now:
        yield f"    [!] derived prices collapse: bid={min_bid} buyNow={buy_now}; skip"
        return False
    yield f"    rating={rating:.1f}  meowbot≈{rec:.0f}  →  bid={min_bid}  buyNow={buy_now}"

    body = build_listing_body(card_id, min_bid, buy_now)
    resp = client.post("/cardmarketplacelistings", json_body=body, confirm_write=True)
    if resp.status_code != 200:
        yield f"    [!] list failed: {resp.status_code} {resp.text[:300]}"
        return False

    yield f"    [+] listed"
    state["listed_card_ids"].append(card_id)
    save_state(state)
    return True


def run(account="HDERDAR", live=False):
    """Generator version — yields log lines instead of printing."""
    if not WATCHLIST_PATH.exists():
        yield f"[X] missing {WATCHLIST_PATH}"
        return
    items = json.loads(WATCHLIST_PATH.read_text())
    watchlist = [it for it in items if it.get("enabled", True)]

    fp = get_account(account)
    min_gap, max_gap = CADENCE_WRITE
    client = RateLimitedClient(fp, min_gap_s=min_gap, max_gap_s=max_gap, dry_run=not live)
    state = load_state()
    yield f"[i] account={account}  live={live}  watchlist={len(watchlist)} pass(es)"

    n_listed = 0
    for entry in watchlist:
        listed = yield from _list_pass_entry_gen(client, entry, state)
        if listed:
            n_listed += 1

    yield f"\n[i] done — listed {n_listed} pass(es)"


if __name__ == "__main__":
    sys.exit(main())
