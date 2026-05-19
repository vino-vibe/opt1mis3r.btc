"""
boost.py — apply a random stat boost to each player pass on file for a sport.

NOTE: per project owner as of 2026-05-17, the boost endpoint is broken upstream;
your friend is investigating. The script is patched and ready but expect 4xx/5xx
from the server until the fix lands.

Patched to:
  * use accounts.py (no hardcoded AUTH_INFO)
  * route through RateLimitedClient (4-8.5s jitter, sentry headers,
    AND the previously-missing real-native-request-token header)
  * dry-run by default; --live to mutate
"""
from __future__ import annotations

import argparse
import json
import random
from pathlib import Path

from accounts import get_account
from client import CADENCE_WRITE, RateLimitedClient

BOOST_KEYS = [1, 2, 3, 4, 5, 21]
BOOST_RARITY = 3
MAPPINGS = {1: "PTS", 2: "AST", 3: "REB", 4: "STL", 5: "BLK", 21: "3PM"}


def load_players(player_file: Path) -> list[dict]:
    with player_file.open(encoding="utf-8") as f:
        return json.load(f).get("passes", [])


def boost_player(client: RateLimitedClient, player: dict) -> tuple[bool, str]:
    pid = player.get("id")
    label = player.get("label", "unknown")
    key = random.choice(BOOST_KEYS)
    path = f"/userpassboostercards/{pid}/rarity/{BOOST_RARITY}"
    resp = client.put(path, json_body={"statBoostKey": str(key)}, confirm_write=True)
    if resp.status_code == 200:
        return True, f"boosted {label} userPassId={pid} {MAPPINGS[key]}"
    try:
        err = resp.json().get("message", resp.text)
    except (json.JSONDecodeError, ValueError):
        err = resp.text
    return False, (
        f"failed {label} userPassId={pid} statBoostKey={key} "
        f"status={resp.status_code} error={err}"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--account", default="HDERDAR")
    parser.add_argument("--sport", default="nba")
    parser.add_argument("--live", action="store_true")
    args = parser.parse_args()

    fp = get_account(args.account)
    min_gap, max_gap = CADENCE_WRITE
    client = RateLimitedClient(fp, min_gap_s=min_gap, max_gap_s=max_gap, dry_run=not args.live)

    player_file = Path("players") / f"{args.account}_{args.sport}.json"
    if not player_file.exists():
        print(f"[X] missing {player_file}; run `python get_players.py` first")
        return

    players = [p for p in load_players(player_file) if p.get("sport") == args.sport]
    print(f"[i] {args.account}/{args.sport}: {len(players)} player(s)  live={args.live}")

    out_dir = Path("boosts")
    out_dir.mkdir(exist_ok=True)
    results = []
    for p in players:
        ok, msg = boost_player(client, p)
        print(msg)
        results.append({"playerId": p.get("id"), "playerLabel": p.get("label"),
                        "success": ok, "message": msg})

    out_path = out_dir / f"{args.account}_{args.sport}_boosts.json"
    with out_path.open("w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    print(f"\nResults saved to {out_path}")


if __name__ == "__main__":
    main()
