"""
boost.py — apply stat boosts to player passes declared in watchlist_boost.json.

For each enabled entry:
  1. Skip if already boosted today (state/boosted_{account}_YYYY-MM-DD.json).
  2. GET /userpasses/{cardId} — check what stat is currently applied.
     If the preferred stat is already active, skip (PUT is a toggle; applying
     the same stat twice removes it).
  3. PUT /userpassboostercards/{cardId}/rarity/{rarity} with the preferred stat key.
     Rarity is per-entry (default 3 = Rare). Set "rarity": 4 in the watchlist
     to allow Epic; leave at 3 to reserve Epic/Legendary for playoffs.
  4. On 200 → record cardId in today's state file.
     On non-200 → log the error and skip.

preferred_stat may be "auto": boost.py fetches the account's Rare booster
inventory for the sport and picks the stat with the highest count.

Dry-run by default. Pass --live to actually mutate.

Usage:
    python boost.py                            # dry-run, HDERDAR only
    python boost.py --live                     # actually boost, HDERDAR only
    python boost.py --account VINO --live      # single named account
    python boost.py --all-accounts --live           # loop every account in ACCOUNTS
    python boost.py --all-accounts --sport wnba --live  # one sport, all accounts

Schedule-lock behaviour:
  Golf has consistent scheduling — one lock means the whole sport is off. The
  first golf failure short-circuits all remaining golf entries for all accounts.
  Other sports (WNBA, NBA, MLB) are player-specific — a locked player is noted
  and skipped on subsequent accounts, but other players on those accounts are
  still attempted.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path

from accounts import get_account, get_all_accounts, AccountFingerprint
from client import CADENCE_WRITE, RateLimitedClient

STATE_DIR  = Path("state")
STATE_DIR.mkdir(exist_ok=True)
WATCHLIST_PATH = Path("watchlist_boost.json")
PLAYERS_DIR    = Path("players")

RARITY_LABELS: dict[int, str] = {3: "Rare", 4: "Epic", 5: "Legendary"}

# Sports where one locked player means the whole sport is off for everyone.
# Golf has consistent tournament scheduling — if one card is locked, all are.
# WNBA/NBA/MLB are player-specific; track ineligible entityIds instead.
SPORTS_WITH_CONSISTENT_SCHEDULING: set[str] = {"golf"}

# Module-level lock state — persists across accounts in the same process run.
_sport_hardlocked: set[str] = set()   # golf: first lock stops all subsequent golf
_entity_locked: set[int]   = set()    # wnba/etc: locked entityIds skipped on later accounts

STAT_KEYS: dict[str, str] = {
    # Basketball
    "PTS":    "1",
    "AST":    "2",
    "REB":    "3",
    "STL":    "4",
    "BLK":    "5",
    "3PM":    "21",
    # Golf
    "EAGLE":  "12",
    "BIRDIE": "11",
    # Baseball
    "K":      "70",
    "R":      "5",
    "RBI":    "3",
    "2B":     "10",
    "HR_3B":  "2_11",
}
KEY_TO_STAT: dict[str, str] = {v: k for k, v in STAT_KEYS.items()}

DEFAULT_RARITY = 3  # Rare — saves Epic/Legendary for playoffs


# ---------------------------------------------------------------------------
# State helpers (per-account so accounts don't share a skip list)
# ---------------------------------------------------------------------------

def state_path(account_name: str) -> Path:
    return STATE_DIR / f"boosted_{account_name}_{date.today().isoformat()}.json"


def load_state(account_name: str) -> dict:
    p = state_path(account_name)
    if p.exists():
        return json.loads(p.read_text())
    return {"boosted_card_ids": []}


def save_state(account_name: str, state: dict) -> None:
    state_path(account_name).write_text(json.dumps(state, indent=2))


# ---------------------------------------------------------------------------
# Watchlist
# ---------------------------------------------------------------------------

def load_watchlist() -> list[dict]:
    if not WATCHLIST_PATH.exists():
        print(f"[X] missing {WATCHLIST_PATH}")
        sys.exit(2)
    items = json.loads(WATCHLIST_PATH.read_text())
    enabled = [it for it in items if it.get("enabled", True)]
    for it in enabled:
        stat = it.get("preferred_stat", "")
        if stat != "auto" and stat not in STAT_KEYS:
            print(f"[X] unknown preferred_stat '{stat}' for {it.get('label')}. "
                  f"Valid: {', '.join(STAT_KEYS)} or 'auto'")
            sys.exit(2)
    return enabled


def build_entity_map(account_name: str, sport: str) -> dict[int, int]:
    """Return {entityId: cardId} from saved player data for this account+sport."""
    player_file = PLAYERS_DIR / f"{account_name}_{sport}.json"
    if not player_file.exists():
        return {}
    data = json.loads(player_file.read_text())
    return {p["entityId"]: p["id"] for p in data.get("passes", [])}


# ---------------------------------------------------------------------------
# Booster inventory (for "auto" stat selection and fallback checks)
# ---------------------------------------------------------------------------

# Raw counts cache: "{account}:{sport}:{rarity}" → {api_key: count}
# Fetched once per account+sport+rarity per run; best-stat derived fresh each call
# so inventory changes mid-run (boosters being consumed) are reflected immediately.
_counts_cache: dict[str, dict[str, int]] = {}


def _fetch_inventory_counts(
    client: RateLimitedClient,
    fp: AccountFingerprint,
    sport: str,
    target_rarity: int,
) -> dict[str, int]:
    """Return {api_key: count} for target_rarity. Cached per account+sport+rarity."""
    cache_key = f"{fp.name}:{sport}:{target_rarity}"
    if cache_key in _counts_cache:
        return _counts_cache[cache_key]

    if not fp.numeric_id:
        print(f"  [!] numeric_id missing for {fp.name} — cannot fetch inventory")
        return {}

    resp = client.get(
        f"/userpassboostercards/{fp.numeric_id}/entity/player",
        params={"displayType": "userpass", "sport": sport, "version": "stat"},
    )
    if resp.status_code != 200:
        print(f"  [!] inventory fetch failed: {resp.status_code}")
        return {}

    data = resp.json()
    groups = data.get("boosterCardInfo", {}).get("rarityGroups", [])
    group = next((g for g in groups if g.get("rarity") == target_rarity), None)
    counts: dict[str, int] = {}
    if group:
        counts = {k: v["count"] for k, v in group.get("statBoostInfo", {}).items()}
    _counts_cache[cache_key] = counts
    return counts


def get_auto_stat(
    client: RateLimitedClient,
    fp: AccountFingerprint,
    sport: str,
    target_rarity: int,
) -> str | None:
    """Return the stat name with the most booster cards at target_rarity."""
    counts = _fetch_inventory_counts(client, fp, sport, target_rarity)
    if not counts:
        return None
    best_key = max(counts, key=counts.get)
    return KEY_TO_STAT.get(best_key)


def stat_is_available(
    client: RateLimitedClient,
    fp: AccountFingerprint,
    sport: str,
    target_rarity: int,
    stat_name: str,
) -> bool:
    """Return True if the account has at least one booster for stat_name at target_rarity."""
    api_key = STAT_KEYS.get(stat_name)
    if not api_key:
        return False
    counts = _fetch_inventory_counts(client, fp, sport, target_rarity)
    return counts.get(api_key, 0) > 0


# ---------------------------------------------------------------------------
# Current pass state
# ---------------------------------------------------------------------------

def get_applied_boost(client: RateLimitedClient, card_id: int) -> tuple[str | None, int | None]:
    """
    Return (stat_name, rarity) for the currently active boost, or (None, None).
    rarity is the integer rarity of the booster card applied (3=Rare, 4=Epic, 5=Legendary).
    """
    resp = client.get(f"/userpasses/{card_id}")
    if resp.status_code != 200:
        print(f"  [!] pass fetch failed: {resp.status_code} {resp.text[:200]}")
        return None, None
    payload = resp.json()
    pass_obj = payload.get("pass") or {}
    boost_card_info = pass_obj.get("boosterCardInfo")
    if not boost_card_info:
        return None, None
    raw_key  = str(boost_card_info.get("statBoostKey", ""))
    raw_rar  = boost_card_info.get("rarity")
    stat     = KEY_TO_STAT.get(raw_key)
    rarity   = int(raw_rar) if raw_rar is not None else None
    return stat, rarity


# ---------------------------------------------------------------------------
# Boost
# ---------------------------------------------------------------------------

def boost_player(
    client: RateLimitedClient,
    fp: AccountFingerprint,
    entry: dict,
    state: dict,
) -> bool:
    label     = entry["label"]
    card_id   = entry["cardId"]
    sport     = entry.get("sport", "")
    rarity    = entry.get("rarity", DEFAULT_RARITY)
    preferred = entry["preferred_stat"]

    # Resolve stat: "auto" picks most populous; explicit stat falls back to
    # fallback_stat (typically "auto") if the preferred stat is out of stock.
    fallback = entry.get("fallback_stat")
    if preferred == "auto":
        resolved = get_auto_stat(client, fp, sport, rarity)
        if not resolved:
            print(f"[ ] {label}: could not resolve auto stat — skipping")
            return False
        preferred = resolved
        print(f"    auto→ {preferred}")
    elif fallback and not stat_is_available(client, fp, sport, rarity, preferred):
        print(f"    {preferred} inventory empty — falling back to {fallback!r}")
        if fallback == "auto":
            resolved = get_auto_stat(client, fp, sport, rarity)
            if not resolved:
                print(f"[ ] {label}: K out and auto fallback failed — skipping")
                return False
            preferred = resolved
            print(f"    fallback auto→ {preferred}")
        else:
            preferred = fallback

    fallback_rarity = entry.get("fallback_rarity")
    if fallback_rarity is not None and rarity != fallback_rarity:
        if not stat_is_available(client, fp, sport, rarity, preferred):
            print(f"    {RARITY_LABELS.get(rarity, rarity)} {preferred} inventory empty — trying {RARITY_LABELS.get(fallback_rarity, fallback_rarity)}")
            rarity = fallback_rarity
            if not stat_is_available(client, fp, sport, rarity, preferred):
                print(f"[ ] {label}: {preferred} unavailable at both rarities — skipping")
                return False

    if card_id in state["boosted_card_ids"]:
        print(f"[ ] {label} (card {card_id}): already boosted today; skip")
        return False

    print(f"[?] {label} (card {card_id})  preferred={preferred}  target_rarity={RARITY_LABELS.get(rarity, rarity)}")

    applied, applied_rarity = get_applied_boost(client, card_id)
    if applied:
        rar_label = RARITY_LABELS.get(applied_rarity, f"rarity-{applied_rarity}")
        print(f"    currently applied: {applied} ({rar_label})")
    else:
        print(f"    currently applied: None")

    # Compare by API key to avoid cross-sport name collisions (BLK/R both="5", REB/RBI both="3")
    if STAT_KEYS.get(applied, "") == STAT_KEYS.get(preferred, ""):
        rar_label = RARITY_LABELS.get(applied_rarity, f"rarity-{applied_rarity}")
        if applied_rarity is not None and applied_rarity > rarity:
            print(f"    {preferred} already active at higher rarity ({rar_label}) — skip to preserve")
        else:
            print(f"    {preferred} already active ({rar_label}) — skip (would toggle off)")
        return False

    key  = STAT_KEYS[preferred]
    path = f"/userpassboostercards/{card_id}/rarity/{rarity}"
    resp = client.put(path, json_body={"statBoostKey": key}, confirm_write=True)

    if resp.status_code != 200:
        try:
            err = resp.json().get("message", resp.text)
        except (json.JSONDecodeError, ValueError):
            err = resp.text
        print(f"    [!] boost failed (HTTP {resp.status_code}): {err}")
        return False

    # The API returns HTTP 200 even when the boost is rejected (e.g. tournament
    # lock, card locked during active game). Must check the success field.
    try:
        body = resp.json()
    except (json.JSONDecodeError, ValueError):
        print(f"    [!] response not JSON: {resp.text[:200]}")
        return False

    if not body.get("success", False):
        msg = body.get("message", "no message in response")
        low = msg.lower()
        if any(w in low for w in ("tournament", "game", "lock", "active", "contest", "scheduled")):
            print(f"    [~] blocked — schedule/tournament lock: {msg}")
            if sport in SPORTS_WITH_CONSISTENT_SCHEDULING:
                _sport_hardlocked.add(sport)
                print(f"    [!] hard-locking sport={sport} for this run — all remaining {sport} entries skipped")
            else:
                entity_id = entry.get("entityId")
                if entity_id is not None:
                    _entity_locked.add(entity_id)
        else:
            print(f"    [!] boost rejected by API: {msg}")
        return False

    print(f"    [+] applied {preferred} (key={key}, rarity={rarity})")
    state["boosted_card_ids"].append(card_id)
    save_state(fp.name, state)
    return True


# ---------------------------------------------------------------------------
# Per-account run
# ---------------------------------------------------------------------------

def run_account(fp: AccountFingerprint, watchlist: list[dict], live: bool) -> int:
    min_gap, max_gap = CADENCE_WRITE
    client = RateLimitedClient(fp, min_gap_s=min_gap, max_gap_s=max_gap, dry_run=not live)
    state  = load_state(fp.name)

    entity_maps: dict[str, dict[int, int]] = {}
    resolved: list[dict] = []

    for entry in watchlist:
        sport = entry["sport"]
        if sport not in entity_maps:
            entity_maps[sport] = build_entity_map(fp.name, sport)

        if "cardId" not in entry:
            entity_id = entry.get("entityId")
            card_id = entity_maps[sport].get(entity_id)
            if card_id is None:
                print(f"[ ] {entry['label']}: not in players/{fp.name}_{sport}.json — skip")
                print()
                continue
            entry = {**entry, "cardId": card_id}

        resolved.append(entry)

    print(f"\n{'='*60}")
    print(f"[i] account={fp.name}  live={live}  resolved={len(resolved)}/{len(watchlist)}")
    print(f"{'='*60}")

    n_boosted = 0
    for entry in resolved:
        sport     = entry.get("sport", "")
        entity_id = entry.get("entityId")

        if sport in _sport_hardlocked:
            print(f"[ ] {entry['label']}: {sport} is hard-locked this run — skip")
            print()
            continue

        if entity_id is not None and entity_id in _entity_locked:
            print(f"[ ] {entry['label']}: entityId {entity_id} locked on earlier account — skip")
            print()
            continue

        if boost_player(client, fp, entry, state):
            n_boosted += 1
        print()

    print(f"[i] {fp.name} done — boosted {n_boosted} pass(es)")
    return n_boosted


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    grp = parser.add_mutually_exclusive_group()
    grp.add_argument("--account", default=None, help="run for one named account")
    grp.add_argument("--all-accounts", action="store_true",
                     help="loop every account declared in ACCOUNTS (default: HDERDAR)")
    parser.add_argument("--live", action="store_true",
                        help="actually apply boosts (default: dry-run)")
    parser.add_argument("--watchlist", default=None,
                        help="override watchlist file (default: watchlist_boost.json)")
    parser.add_argument("--sport", default=None,
                        help="filter to a single sport (e.g. golf, wnba)")
    args = parser.parse_args()

    if args.all_accounts:
        fps = get_all_accounts()
    elif args.account:
        fps = [get_account(args.account)]
    else:
        fps = [get_account("HDERDAR")]

    global WATCHLIST_PATH
    if args.watchlist:
        WATCHLIST_PATH = Path(args.watchlist)

    watchlist = load_watchlist()
    if args.sport:
        watchlist = [e for e in watchlist if e.get("sport") == args.sport]
        if not watchlist:
            print(f"[X] no enabled entries for sport={args.sport!r}")
            return 2

    total = 0
    for fp in fps:
        total += run_account(fp, watchlist, args.live)

    print(f"\n[i] grand total — {total} boost(s) across {len(fps)} account(s)")
    return 0


def _boost_player_gen(client, fp, entry, state):
    """Sub-generator: yields log lines, returns True if boost was applied."""
    label = entry["label"]
    card_id = entry["cardId"]
    sport = entry.get("sport", "")
    rarity = entry.get("rarity", DEFAULT_RARITY)
    preferred = entry["preferred_stat"]
    fallback = entry.get("fallback_stat")

    if preferred == "auto":
        resolved = get_auto_stat(client, fp, sport, rarity)
        if not resolved:
            yield f"[ ] {label}: could not resolve auto stat — skipping"
            return False
        preferred = resolved
        yield f"    auto→ {preferred}"
    elif fallback and not stat_is_available(client, fp, sport, rarity, preferred):
        yield f"    {preferred} inventory empty — falling back to {fallback!r}"
        if fallback == "auto":
            resolved = get_auto_stat(client, fp, sport, rarity)
            if not resolved:
                yield f"[ ] {label}: K out and auto fallback failed — skipping"
                return False
            preferred = resolved
            yield f"    fallback auto→ {preferred}"
        else:
            preferred = fallback

    fallback_rarity = entry.get("fallback_rarity")
    if fallback_rarity is not None and rarity != fallback_rarity:
        if not stat_is_available(client, fp, sport, rarity, preferred):
            yield f"    {RARITY_LABELS.get(rarity, rarity)} {preferred} inventory empty — trying {RARITY_LABELS.get(fallback_rarity, fallback_rarity)}"
            rarity = fallback_rarity
            if not stat_is_available(client, fp, sport, rarity, preferred):
                yield f"[ ] {label}: {preferred} unavailable at both rarities — skipping"
                return False

    if card_id in state["boosted_card_ids"]:
        yield f"[ ] {label} (card {card_id}): already boosted today; skip"
        return False

    yield f"[?] {label} (card {card_id})  preferred={preferred}  target_rarity={RARITY_LABELS.get(rarity, rarity)}"

    resp = client.get(f"/userpasses/{card_id}")
    if resp.status_code != 200:
        yield f"  [!] pass fetch failed: {resp.status_code} {resp.text[:200]}"
        return False
    pass_payload = resp.json()
    pass_obj = pass_payload.get("pass") or {}
    boost_card_info = pass_obj.get("boosterCardInfo")
    if boost_card_info:
        raw_key = str(boost_card_info.get("statBoostKey", ""))
        raw_rar = boost_card_info.get("rarity")
        # Use preferred's key to reverse-lookup the name when keys collide across sports
        # (BLK and R both map to key "5"; REB and RBI both map to key "3").
        applied = (preferred if raw_key == STAT_KEYS.get(preferred, "") else KEY_TO_STAT.get(raw_key))
        applied_rarity = int(raw_rar) if raw_rar is not None else None
    else:
        applied, applied_rarity, raw_key = None, None, ""

    if applied:
        rar_label = RARITY_LABELS.get(applied_rarity, f"rarity-{applied_rarity}")
        yield f"    currently applied: {applied} ({rar_label})"
    else:
        yield f"    currently applied: None"

    if raw_key == STAT_KEYS.get(preferred, ""):
        rar_label = RARITY_LABELS.get(applied_rarity, f"rarity-{applied_rarity}")
        if applied_rarity is not None and applied_rarity > rarity:
            yield f"    {preferred} already active at higher rarity ({rar_label}) — skip to preserve"
        else:
            yield f"    {preferred} already active ({rar_label}) — skip (would toggle off)"
        return False

    key = STAT_KEYS[preferred]
    path = f"/userpassboostercards/{card_id}/rarity/{rarity}"
    resp = client.put(path, json_body={"statBoostKey": key}, confirm_write=True)

    if resp.status_code != 200:
        try:
            err = resp.json().get("message", resp.text)
        except (json.JSONDecodeError, ValueError):
            err = resp.text
        yield f"    [!] boost failed (HTTP {resp.status_code}): {err}"
        return False

    try:
        body = resp.json()
    except (json.JSONDecodeError, ValueError):
        yield f"    [!] response not JSON: {resp.text[:200]}"
        return False

    if not body.get("success", False):
        msg = body.get("message", "no message in response")
        low = msg.lower()
        if any(w in low for w in ("tournament", "game", "lock", "active", "contest", "scheduled")):
            yield f"    [~] blocked — schedule/tournament lock: {msg}"
            if sport in SPORTS_WITH_CONSISTENT_SCHEDULING:
                _sport_hardlocked.add(sport)
                yield f"    [!] hard-locking sport={sport} for this run — all remaining {sport} entries skipped"
            else:
                entity_id = entry.get("entityId")
                if entity_id is not None:
                    _entity_locked.add(entity_id)
        else:
            yield f"    [!] boost rejected by API: {msg}"
        return False

    yield f"    [+] applied {preferred} (key={key}, rarity={rarity})"
    state["boosted_card_ids"].append(card_id)
    save_state(fp.name, state)
    return True


def run(account=None, all_accounts=False, live=False, sport=None):
    """Generator version — yields log lines instead of printing. Resets module globals."""
    global _sport_hardlocked, _entity_locked, _counts_cache
    _sport_hardlocked = set()
    _entity_locked = set()
    _counts_cache = {}

    if all_accounts:
        fps = get_all_accounts()
    elif account:
        fps = [get_account(account)]
    else:
        fps = [get_account("HDERDAR")]

    if not WATCHLIST_PATH.exists():
        yield f"[X] missing {WATCHLIST_PATH}"
        return
    items = json.loads(WATCHLIST_PATH.read_text())
    enabled = [it for it in items if it.get("enabled", True)]

    for it in enabled:
        stat = it.get("preferred_stat", "")
        if stat != "auto" and stat not in STAT_KEYS:
            yield (f"[X] unknown preferred_stat '{stat}' for {it.get('label')}. "
                   f"Valid: {', '.join(STAT_KEYS)} or 'auto'")
            return

    watchlist = enabled
    if sport:
        watchlist = [e for e in watchlist if e.get("sport") == sport]
        if not watchlist:
            yield f"[X] no enabled entries for sport={sport!r}"
            return

    grand_total = 0
    for fp in fps:
        min_gap, max_gap = CADENCE_WRITE
        client = RateLimitedClient(fp, min_gap_s=min_gap, max_gap_s=max_gap, dry_run=not live)
        state = load_state(fp.name)

        entity_maps: dict[str, dict[int, int]] = {}
        resolved: list[dict] = []
        for entry in watchlist:
            sp = entry["sport"]
            if sp not in entity_maps:
                entity_maps[sp] = build_entity_map(fp.name, sp)
            if "cardId" not in entry:
                entity_id = entry.get("entityId")
                card_id = entity_maps[sp].get(entity_id)
                if card_id is None:
                    yield f"[ ] {entry['label']}: not in players/{fp.name}_{sp}.json — skip"
                    yield ""
                    continue
                entry = {**entry, "cardId": card_id}
            resolved.append(entry)

        yield f"\n{'='*60}"
        yield f"[i] account={fp.name}  live={live}  resolved={len(resolved)}/{len(watchlist)}"
        yield f"{'='*60}"

        n_boosted = 0
        for entry in resolved:
            sp = entry.get("sport", "")
            entity_id = entry.get("entityId")

            if sp in _sport_hardlocked:
                yield f"[ ] {entry['label']}: {sp} is hard-locked this run — skip"
                yield ""
                continue
            if entity_id is not None and entity_id in _entity_locked:
                yield f"[ ] {entry['label']}: entityId {entity_id} locked on earlier account — skip"
                yield ""
                continue

            boosted = yield from _boost_player_gen(client, fp, entry, state)
            if boosted:
                n_boosted += 1
            yield ""

        yield f"[i] {fp.name} done — boosted {n_boosted} pass(es)"
        grand_total += n_boosted

    yield f"\n[i] grand total — {grand_total} boost(s) across {len(fps)} account(s)"


if __name__ == "__main__":
    sys.exit(main())
