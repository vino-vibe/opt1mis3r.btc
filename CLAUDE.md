# opt1mis3r — project status (2026-05-23)

## What this is

A local CLI automation agent for the Real Sports app. It runs a daily ritual —
buy player packs, claim OTD historical earnings, list passes on the marketplace
once they hit the rare rating threshold, and apply stat boosts from a per-player
watchlist. All scripts run on your Mac, no cloud, no shared infra.

---

## What works (shippable today)

| Module | File | Notes |
|---|---|---|
| Auth headers + rate limiting | `client.py` | Sentry-trace/baggage, native+request tokens, per-call jitter |
| Account fingerprint config | `accounts.py` | Reads `.env`; per-account UUID/device/version/numeric_id with fallbacks |
| Token generation | `token_generation.py` | HMAC-SHA256 native token + Hashids request token |
| OTD fetch | `get_claims.py` | Saves `claims/{account}_claims_{date}.json` |
| OTD claim | `do_claims.py` | Rate-limited PUT per sport, dry-run default, respects `claimsRemaining` |
| Player pass lookup | `get_players.py` | Fetches all sports, saves `players/{account}_{sport}.json` |
| Pack buying | `buy_packs.py` | Full buy flow confirmed — body shape captured 2026-05-17 |
| Marketplace listing | `list_pass.py` | Rarity gate (≥80), meowbot pricing, tick rounding, idempotent |
| Meowbot pricing | `meowbot.py` | Supabase market-data; computes `rating × twAvgRR` |
| Tick rounding | `pricing.py` | 100-tick below 2000 rax, 500-tick at 2000+ rax |
| Boost | `boost.py` | Watchlist-driven, preferred stat per player, toggle-safe, idempotent |

---

## App version (current as of 2026-05-22)

- `real-version: 32` (was 31)
- `sentry-release: vg.real-10.150` (was vg.real-10.145)
- Update `.env`: `HDERDAR_APP_VERSION=32`, `SENTRY_RELEASE=vg.real-10.150`

---

## API shapes confirmed (from ProxyPin captures)

- `GET /collectingpacks/player?entityId=X&season=Y&sport=Z` — price, `purchaseDisabledMessage`
- `POST /collectingpacks/player` — body: `{sport, season (string), cost, acceptPriceChanges: true, entityId (string)}`
- `GET /cardhistoricalearnings?day=YYYY-MM-DD` — OTD claim list
- `PUT /cardhistoricalearnings` — body: `{userPassId}`
- `GET /userpasses/{userId}/passes` — player pass list per sport
- `GET /userpasses/{cardId}` — pass state: `boostValue`, `boostInfo.baseRarity`, `boosterCardInfo`
- `POST /cardmarketplacelistings` — listing body confirmed; `durationInHours: 72` confirmed
- `PUT /userpassboostercards/{cardId}/rarity/{rarity}` — body: `{statBoostKey}`; toggle (same call applies and removes)
- `GET /collectingpacks/wnba/season/2026/shopinfo?entityId=X&entityType=player&source=userpasscontrol` — alternative WNBA pack endpoint (request captured; response pending)

---

## Still uncaptured / blocked

| # | What | Blocks |
|---|---|---|
| 1 | 3rd OTD bet endpoint | Morning ritual step 3 |
| 2 | Real Pro account flag (which field, which endpoint) | Gating step 3 on Pro status |
| 3 | Alternative listing durations | Randomizing duration (currently hardcoded 72h) |
| 4 | `POST /cardmarketplacelistings/{id}/bid` body | Player pass scanner |
| 5 | Listings GET pagination params | Scanner page-through |
| 6 | "Top bid is mine" field on listing object | Avoid self-overbidding in scanner |
| 7 | WNBA pack shopinfo response | Confirming correct endpoint format for WNBA packs |

---

## Boost design note

The boost inventory GET (`/userpassboostercards/{numericId}/entity/player`) was
captured from a different account. Rather than block on finding HDERDAR's numeric
ID, `boost.py` was simplified: no pre-flight inventory check. It attempts the
preferred stat PUT directly; on failure it logs the error and skips. Update
`preferred_stat` in `watchlist_boost.json` manually if a stat category runs out.
`HDERDAR_NUMERIC_ID` stays in `.env` / `AccountFingerprint` for future use.

---

## Not started yet

- **Daily orchestrator** — randomized morning start window (07:00–09:30), sequences all modules with inter-step delay. This is the next build priority.
- **Player pass scanner** — browse marketplace for undervalued passes, score deals vs meowbot price, bid. Second priority; see `Project_vision.md`.
- **Interstitial reads** — fire GET /home or GET /userpasses/{id} between writes to better simulate a human session (RED_FLAGS.md #12).

---

## Detection surface summary

All CRIT and HIGH items in `RED_FLAGS.md` are fixed. Open MED items:
- #11 — daily run at randomized time (solved by orchestrator when built)
- #12 — interstitial reads between writes
- #15 — boost stat is now per-player preferred, not uniform-random
- #16 — listing price multipliers are tunable per watchlist entry (planned)
- #17 — listing duration hardcoded 72h; needs alternatives captured first

---

## GUI

Streamlit dashboard (`app.py`) was explored but the setup wasn't working. Parked as a future idea. Everything runs CLI-only for now. `app.py`, `GUI_SETUP.md`, and `run_gui.sh` have been removed.

---

## Build sequence (remaining)

1. ~~Listing module~~ — done
2. ~~Pack-buy module~~ — done
3. ~~Buy → list pipeline with watchlists~~ — done (separate CLI scripts)
4. ~~Boost framework~~ — done
5. **Daily orchestrator** — randomized morning trigger, sequenced modules
6. 3rd OTD bet — after endpoint capture
7. Real Pro detection + gating
8. Player pass scanner — after morning ritual ships reliably
