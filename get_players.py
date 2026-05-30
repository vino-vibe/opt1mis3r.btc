"""
get_players.py — fetch the user's pass list per sport, save to players/<name>_<sport>.json.

Patched to:
  * use accounts.py (no hardcoded AUTH_INFOS dict)
  * route through RateLimitedClient (4-8.5s jitter, sentry headers)
  * iterate accounts × sports with rate limiting between every call
"""
import json
import time
from pathlib import Path

from accounts import get_all_accounts
from client import RateLimitedClient

SPORTS = ["nhl", "nba", "mlb", "wnba", "golf"]


def main() -> None:
    out_dir = Path("players")
    out_dir.mkdir(exist_ok=True)

    for fp in get_all_accounts():
        user_id = fp.auth_info.split("!")[0]
        client = RateLimitedClient(fp)
        print(f"Fetching players for {fp.name} (userId={user_id})...")

        for sport in SPORTS:
            params = {
                "entityType": "player",
                "season": 2026 if sport != "nhl" else 2025,
                "sport": sport,
                "_": int(time.time() * 1000),
            }
            print(f"  -> {sport}")
            resp = client.get(f"/userpasses/{user_id}/passes", params=params)
            if resp.status_code != 200:
                print(f"  [!] {sport}: status={resp.status_code} {resp.text[:200]}")
                continue
            out_path = out_dir / f"{fp.name}_{sport}.json"
            with out_path.open("w", encoding="utf-8") as f:
                json.dump(resp.json(), f, indent=2, ensure_ascii=False)
        print()


def run():
    """Generator version of main() — yields log lines instead of printing."""
    out_dir = Path("players")
    out_dir.mkdir(exist_ok=True)
    for fp in get_all_accounts():
        user_id = fp.auth_info.split("!")[0]
        client = RateLimitedClient(fp)
        yield f"Fetching players for {fp.name} (userId={user_id})..."
        for sport in SPORTS:
            params = {
                "entityType": "player",
                "season": 2026 if sport != "nhl" else 2025,
                "sport": sport,
                "_": int(time.time() * 1000),
            }
            yield f"  -> {sport}"
            resp = client.get(f"/userpasses/{user_id}/passes", params=params)
            if resp.status_code != 200:
                yield f"  [!] {sport}: status={resp.status_code} {resp.text[:200]}"
                continue
            out_path = out_dir / f"{fp.name}_{sport}.json"
            with out_path.open("w", encoding="utf-8") as f:
                json.dump(resp.json(), f, indent=2, ensure_ascii=False)
        yield ""


if __name__ == "__main__":
    main()
