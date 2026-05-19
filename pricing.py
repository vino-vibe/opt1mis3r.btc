"""
pricing.py — Real marketplace listing tick rounding.

The mobile UI restricts listing prices to a discrete set:
  • below 1000    → ticks of 100 (assumed; capture if you ever list <1000)
  • 1000–2000     → ticks of 100
  • 2000+         → ticks of 500

Use round_up_tick for buyNowPrice (you want at least the target).
Use round_down_tick for minBidPrice (you want at most the target).
"""
from __future__ import annotations


def _tick_size(price: int | float) -> int:
    """Tick size that APPLIES at this price level."""
    if price >= 2000:
        return 500
    return 100


def round_up_tick(price: float) -> int:
    """Round price UP to the nearest valid tick. Used for buy-now."""
    if price <= 0:
        return 0
    # Check whether the price falls exactly on a 100-tick boundary that
    # would still be valid even though >= 2000 in some edge cases. The rule
    # change happens AT 2000, so 2000 itself is a valid value at 500-tick.
    step = _tick_size(price)
    # If we're rounding up across the 2000 boundary, snap to 2000 first.
    if price < 2000 and (price + (-price % 100)) > 2000:
        return 2000
    rem = price % step
    if rem == 0:
        return int(price)
    return int(price + (step - rem))


def round_down_tick(price: float) -> int:
    """Round price DOWN to the nearest valid tick. Used for starting bid."""
    if price <= 0:
        return 0
    step = _tick_size(price)
    # If rounding down crosses 2000, snap to 2000 (a valid value at both levels).
    if price >= 2000 and (price - (price % 500)) < 2000:
        return 2000
    rem = price % step
    return int(price - rem)


# --- quick self-test --------------------------------------------------------
if __name__ == "__main__":
    cases_up = [
        (3144.6, 3500),    # Ohtani-rare meowbot price * 1.10 → 3458 → 3500
        (2000, 2000),
        (2001, 2500),
        (1850, 1900),
        (1000, 1000),
        (999, 1000),
        (100, 100),
        (105, 200),
    ]
    cases_down = [
        (2829.6, 2500),    # Ohtani-rare meowbot price * 0.90 → 2829 → 2500
        (2000, 2000),
        (1999, 1900),
        (1100, 1100),
        (1101, 1100),
        (3500, 3500),
        (3499, 3000),
    ]
    fail = 0
    for p, exp in cases_up:
        got = round_up_tick(p)
        ok = got == exp
        fail += not ok
        print(f"{'OK' if ok else 'FAIL'} round_up_tick({p}) = {got} (expected {exp})")
    for p, exp in cases_down:
        got = round_down_tick(p)
        ok = got == exp
        fail += not ok
        print(f"{'OK' if ok else 'FAIL'} round_down_tick({p}) = {got} (expected {exp})")
    print(f"\n{fail} failure(s)" if fail else "\nall ok")
