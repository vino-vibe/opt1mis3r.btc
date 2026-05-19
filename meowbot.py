"""
meowbot.py — fetch meowbot/realapp.tools bulk-sales prices.

API surface discovered from the realapp.tools SPA on 2026-05-17:
  POST https://mfsyhtuqybbxprgwwykd.supabase.co/functions/v1/market-data
  body: {"action": "get_play_card_market_summary", "payload": {"entityId": N, "season": Y}}

Response shape:
  {
    "entityId": 660271,
    "season": 2026,
    "bulk": {
      "byRarity": [
        {
          "rarity": 3,                    # 3=Rare, 4=Epic, 5=Legendary, 6=Mystic, 7=Iconic
          "sampleCount": 3570,
          "liveCount": 5,
          "endedCount": 3565,
          "floorPrice": 2100,             # current lowest live listing
          "avgPrice": 3996.99,            # raw average
          "avgRaxPerRating": 44.45,
          "twAvgRr": 39.30                # time-weighted average rax/rating ← THIS is what realapp.tools shows
        },
        ...
      ]
    },
    "play": {"byRarity": [], "fetchError": null}
  }

The "Recommended R/R" value shown on the player page = twAvgRr.
The "bulk" listing price for a pass at rating R = R * twAvgRr.
"""
from __future__ import annotations

from dataclasses import dataclass

import requests

MARKET_DATA_URL = "https://mfsyhtuqybbxprgwwykd.supabase.co/functions/v1/market-data"

RARITY_RARE = 3
RARITY_EPIC = 4
RARITY_LEGENDARY = 5
RARITY_MYSTIC = 6
RARITY_ICONIC = 7

# Minimum sample count we'll trust for a recommended price. Below this,
# the time-weighted average is too noisy and we fall back to "no price".
MIN_SAMPLE_COUNT = 20


@dataclass
class BulkRarityStats:
    rarity: int
    sample_count: int
    live_count: int
    floor_price: float | None
    avg_price: float
    avg_rax_per_rating: float
    tw_avg_rr: float          # time-weighted rax/rating — the headline number


@dataclass
class MarketSummary:
    entity_id: int
    season: int
    by_rarity: dict[int, BulkRarityStats]   # keyed by rarity int

    def for_rarity(self, rarity: int) -> BulkRarityStats | None:
        return self.by_rarity.get(rarity)


def fetch_market_summary(entity_id: int, season: int, *, timeout_s: float = 10.0) -> MarketSummary:
    """Hit the meowbot supabase market-data endpoint and parse the bulk summary."""
    resp = requests.post(
        MARKET_DATA_URL,
        json={"action": "get_play_card_market_summary", "payload": {"entityId": entity_id, "season": season}},
        headers={"Content-Type": "application/json"},
        timeout=timeout_s,
    )
    resp.raise_for_status()
    data = resp.json()
    if data.get("error"):
        raise RuntimeError(f"meowbot error for entityId={entity_id} season={season}: {data['error']}")

    by_rarity: dict[int, BulkRarityStats] = {}
    for r in (data.get("bulk") or {}).get("byRarity", []):
        by_rarity[r["rarity"]] = BulkRarityStats(
            rarity=r["rarity"],
            sample_count=r["sampleCount"],
            live_count=r["liveCount"],
            floor_price=r.get("floorPrice"),
            avg_price=r["avgPrice"],
            avg_rax_per_rating=r["avgRaxPerRating"],
            tw_avg_rr=r["twAvgRr"],
        )

    return MarketSummary(
        entity_id=data["entityId"],
        season=data["season"],
        by_rarity=by_rarity,
    )


def recommended_price_for_pass(
    entity_id: int,
    season: int,
    pass_rating: float,
    *,
    rarity: int = RARITY_RARE,
) -> float | None:
    """
    Return the meowbot-derived recommended price for a pass at the given rating.

    Returns None if there aren't enough samples to be trustworthy — the caller
    must decide whether to skip the listing or fall back to a manual override.
    """
    summary = fetch_market_summary(entity_id, season)
    rs = summary.for_rarity(rarity)
    if rs is None or rs.sample_count < MIN_SAMPLE_COUNT:
        return None
    return pass_rating * rs.tw_avg_rr


# --- quick self-test ---------------------------------------------------------
if __name__ == "__main__":
    # Shohei Ohtani 2026 MLB — entityId 660271
    rec = recommended_price_for_pass(660271, 2026, 80.0, rarity=RARITY_RARE)
    print(f"Ohtani 2026 MLB @ 80.0 rating, RARE → recommended {rec:.0f} rax")
    summary = fetch_market_summary(660271, 2026)
    for rarity, rs in sorted(summary.by_rarity.items()):
        print(f"  rarity={rarity} samples={rs.sample_count:>5} floor={rs.floor_price} "
              f"avgPrice={rs.avg_price:>8.0f} twAvgRR={rs.tw_avg_rr:.2f}")
