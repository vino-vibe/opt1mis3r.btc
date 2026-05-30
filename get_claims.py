"""
get_claims.py — fetch the daily cardhistoricalearnings JSON per account.

Patched to:
  * use accounts.py (no hardcoded AUTH_INFOS dict)
  * route through RateLimitedClient (sentry headers, jitter)
  * support --account for single-account runs (GUI parity)
"""
import argparse
import json
import time
from datetime import date
from pathlib import Path

from accounts import get_account, get_all_accounts
from client import RateLimitedClient

DATE = date.today().isoformat()


def fetch_account_claims(client: RateLimitedClient, account_name: str, output_dir: Path) -> None:
    """Fetch historical earnings claims for the given account; save to JSON."""
    cache_buster = int(time.time() * 1000)
    resp = client.get("/cardhistoricalearnings", params={"day": DATE, "_": cache_buster})
    if resp.status_code != 200:
        print(f"{account_name} Error: {resp.status_code} - {resp.text[:300]}")
        return
    output_path = output_dir / f"{account_name}_claims_{DATE}.json"
    with output_path.open("w", encoding="utf-8") as f:
        json.dump(resp.json(), f, indent=2, ensure_ascii=False)
    print(f"{account_name} claims data saved to {output_path}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--account", default=None,
                        help="run for one named account (default: all)")
    args = parser.parse_args()

    output_dir = Path("claims")
    output_dir.mkdir(exist_ok=True)

    fps = [get_account(args.account)] if args.account else get_all_accounts()
    for fp in fps:
        client = RateLimitedClient(fp)
        fetch_account_claims(client, fp.name, output_dir)


def run(account=None):
    """Generator version of main() — yields log lines instead of printing."""
    output_dir = Path("claims")
    output_dir.mkdir(exist_ok=True)
    fps = [get_account(account)] if account else get_all_accounts()
    for fp in fps:
        today = date.today().isoformat()
        client = RateLimitedClient(fp)
        cache_buster = int(time.time() * 1000)
        resp = client.get("/cardhistoricalearnings", params={"day": today, "_": cache_buster})
        if resp.status_code != 200:
            yield f"{fp.name} Error: {resp.status_code} - {resp.text[:300]}"
            continue
        output_path = output_dir / f"{fp.name}_claims_{today}.json"
        with output_path.open("w", encoding="utf-8") as f:
            json.dump(resp.json(), f, indent=2, ensure_ascii=False)
        yield f"{fp.name} claims data saved to {output_path}"


if __name__ == "__main__":
    main()
