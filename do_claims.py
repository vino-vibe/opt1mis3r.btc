"""
do_claims.py — PUT cardhistoricalearnings for each claimable card.

Patched to:
  * use accounts.py (no hardcoded AUTH_INFOS dict)
  * route every PUT through RateLimitedClient (4-8.5s jitter, sentry headers)
  * preserve the existing JSON shape for the claims/*.json input files
"""
import argparse
import json
from datetime import date
from pathlib import Path

from accounts import get_account, get_all_accounts
from client import CADENCE_OTD_CLAIM, AccountFingerprint, RateLimitedClient

DATE = date.today().isoformat()
CLAIMS_DIR = Path("claims")


def claim_account(client: RateLimitedClient, account_name: str, dry_run: bool) -> None:
    claims_path = CLAIMS_DIR / f"{account_name}_claims_{DATE}.json"
    if not claims_path.exists():
        print(f"[{account_name}] missing claims file: {claims_path}")
        return

    with claims_path.open(encoding="utf-8") as f:
        response_data = json.load(f)

    sport_earnings = response_data.get("sportEarnings", [])
    if not sport_earnings:
        print(f"[{account_name}] no sportEarnings in {claims_path}")
        return

    print(f"[{account_name}] processing {len(sport_earnings)} sports  live={not dry_run}")

    for sport_entry in sport_earnings:
        sport_name = sport_entry.get("sport", "unknown")
        pass_earnings = sport_entry.get("passEarnings", [])
        claimable = [pe for pe in pass_earnings if not pe.get("isDisabled", False)]
        if not claimable:
            print(f"[{account_name}] {sport_name}: no claimable cards")
            continue
        claims_remaining = sport_entry.get("claimsRemaining", 0)
        cards_to_claim = claimable[: min(len(claimable), claims_remaining)]
        print(f"[{account_name}] {sport_name}: claiming {len(cards_to_claim)} card(s)")

        for pe in cards_to_claim:
            payload = {"userPassId": pe["id"]}
            resp = client.put("/cardhistoricalearnings", json_body=payload, confirm_write=True)
            label = pe.get("label", "unknown")
            if resp.status_code == 200:
                print(f"  [{account_name}] claimed {label} userPassId={pe['id']}")
            else:
                try:
                    err = resp.json().get("message", resp.text)
                except (json.JSONDecodeError, ValueError):
                    err = resp.text
                print(f"  [{account_name}] FAILED {label} userPassId={pe['id']} "
                      f"status={resp.status_code} err={err}")
        print()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--account", default=None,
                        help="run for one named account (default: all)")
    parser.add_argument("--live", action="store_true",
                        help="actually PUT claims (default: dry-run)")
    args = parser.parse_args()

    fps: list[AccountFingerprint]
    if args.account:
        fps = [get_account(args.account)]
    else:
        fps = get_all_accounts()

    min_gap, max_gap = CADENCE_OTD_CLAIM
    for fp in fps:
        client = RateLimitedClient(fp, min_gap_s=min_gap, max_gap_s=max_gap, dry_run=not args.live)
        claim_account(client, fp.name, dry_run=not args.live)
        print()


if __name__ == "__main__":
    main()
