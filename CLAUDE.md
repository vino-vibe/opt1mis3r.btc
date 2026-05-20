# opt1ms3r — project status (2026-05-19)

## What this is

A local CLI automation agent for the Real Sports app. It runs a daily ritual —
buy player packs, claim OTD historical earnings, list passes on the marketplace
once they hit the rare rating threshold. All scripts run on your Mac, no cloud,
no shared infra.

---

## What works (shippable today)

| Module | File | Notes |
|---|---|---|
| Auth headers + rate limiting | `client.py` | Sentry-trace/baggage, native+request tokens, per-call jitter |
| Account fingerprint config | `accounts.py` | Reads `.env`; per-account UUID/device/version with fallbacks |
| Token generation | `token_generation.py` | HMAC-SHA256 native token + Hashids request token |
| OTD fetch | `get_claims.py` | Saves `claims/{account}_claims_{date}.json` |
| OTD claim | `do_claims.py` | Rate-limited PUT per sport, dry-run default, respects `claimsRemaining` |
| Player pass lookup | `get_players.py` | Fetches all sports, saves `players/{account}_{sport}.json` |
| Pack buying | `buy_packs.py` | Full buy flow confirmed — body shape captured 2026-05-17 |
| Marketplace listing | `list_pass.py` | Rarity gate (≥80), meowbot pricing, tick rounding, idempotent |
| Meowbot pricing | `meowbot.py` | Supabase market-data; computes `rating × twAvgRR` |
| Tick rounding | `pricing.py` | 100-tick below 2000 rax, 500-tick at 2000+ rax |
| Boost | `boost.py` | Script is ready; boost endpoint broken upstream — waiting on friend's fix |

---

## API shapes confirmed (from ProxyPin captures)

- `GET /collectingpacks/player?entityId=X&season=Y&sport=Z` — price, `purchaseDisabledMessage`
- `POST /collectingpacks/player` — body: `{sport, season (string), cost, acceptPriceChanges: true, entityId (string)}`
- `GET /cardhistoricalearnings?day=YYYY-MM-DD` — OTD claim list
- `PUT /cardhistoricalearnings` — body: `{userPassId}`
- `GET /userpasses/{userId}/passes` — player pass list per sport
- `GET /userpasses/{cardId}` — pass state: `boostValue`, `boostInfo.baseRarity`
- `POST /cardmarketplacelistings` — listing body confirmed; `durationInHours: 72` confirmed
- `PUT /userpassboostercards/{id}/rarity/{rarity}` — body: `{statBoostKey}` (endpoint broken server-side)

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
| 7 | Boost endpoint server-side fix | Boost step |

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
- #15 — boost stat weighting per player (not uniform-random)
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
4. **Daily orchestrator** — randomized morning trigger, sequenced modules
5. 3rd OTD bet — after endpoint capture
6. Auto-boost — after friend's fix
7. Real Pro detection + gating
8. Player pass scanner — after morning ritual ships reliably
