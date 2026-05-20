# opt1ms3r

Local automation agent for Real Sports. Runs a daily ritual on your Mac: buy player packs, claim OTD historical earnings, and list passes on the marketplace once they cross the rare rating threshold. Everything is CLI-only, dry-run by default, and designed to look like a real iOS user.

---

## How it works at a high level

The agent is a set of Python scripts that talk to `api.real.vg` using the same headers and token format the Real iOS app sends. Every API call goes through a shared `RateLimitedClient` that enforces randomized timing between calls (4–8.5 seconds by default), generates fresh cryptographic tokens per request, and includes the Sentry tracing headers the iOS app sends on every call.

Each script is a standalone CLI tool you can run individually or chain together. There is no orchestrator yet — that's the next thing to build.

---

## Setup

### 1. Create a virtual environment

```bash
cd opt1ms3r.btc-master
python3 -m venv venv
source venv/bin/activate
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

Dependencies: `requests`, `python-dotenv`, `hashids`. That's it.

### 3. Configure `.env`

Create a `.env` file in the project root. This is the only place credentials and device fingerprints live.

```
# Comma-separated list of account names
ACCOUNTS=HDERDAR

# Per-account auth info (the value of the real-auth-info header from your iPhone)
HDERDAR=<userId>!<token>!<deviceUuid>

# Per-account iPhone fingerprint — match what your phone sends exactly
HDERDAR_DEVICE_UUID=XXXXXXXX-XXXX-XXXX-XXXX-XXXXXXXXXXXX
HDERDAR_DEVICE_NAME=iPhone15,3
HDERDAR_APP_VERSION=31

# Optional: shared fallbacks if you don't set per-account values
DEFAULT_DEVICE_UUID=...
DEFAULT_DEVICE_NAME=iPhone15,3
DEFAULT_APP_VERSION=31

# App version strings — update both when the Real app updates
SENTRY_RELEASE=vg.real-10.145
USER_AGENT_CFNETWORK=3860.400.51
USER_AGENT_DARWIN=25.3.0
```

`HDERDAR_APP_VERSION` and `SENTRY_RELEASE` must match the version of Real currently installed on your phone. If the app updates and you don't update these, the headers will fingerprint you as an older version.

To grab your `real-auth-info`, capture a request from the Real app via ProxyPin and copy the `real-auth-info` header value.

### 4. Verify your setup

```bash
python accounts.py
```

This prints each configured account with its device model, app version, and the first 8 characters of its UUID. If anything is missing from `.env` it will tell you which variable to add.

---

## Architecture

```
token_generation.py   — HMAC-SHA256 native token + Hashids request token (per call)
client.py             — RateLimitedClient: headers, timing, dry-run gate
accounts.py           — AccountFingerprint objects from .env
        |
        ├── get_claims.py     — fetch OTD claim list
        ├── do_claims.py      — PUT each claimable card
        ├── get_players.py    — fetch your pass list per sport
        ├── buy_packs.py      — buy the daily 200-rax pack per watchlisted player
        ├── list_pass.py      — list passes that hit rare (80 rating)
        │       └── meowbot.py / pricing.py   — price lookups + tick rounding
        └── boost.py          — apply stat boosts (endpoint broken upstream)
```

Every script imports from `accounts.py` to get fingerprints and from `client.py` to make API calls. No script hardcodes auth info or builds headers itself.

---

## Token generation

The Real API requires two tokens on every request, both generated fresh per call by `token_generation.py`.

**Native request token** (`real-native-request-token`):
1. Take the current Unix timestamp in milliseconds.
2. Generate an 8-character nonce from a UUID.
3. Build the message string: `{timestamp_ms}.{nonce}`.
4. HMAC-SHA256 sign that message with the app's embedded key, take the first 16 bytes of the digest, base64-encode it.
5. Final token: `{timestamp_ms}.{nonce}.{signature}`

**Request token** (`real-request-token`):
Hashids-encode the same millisecond timestamp using the app's salt and a minimum length of 16. Produces a compact alphanumeric string.

These tokens are regenerated on every outbound call. The server uses them to detect replay attacks and to verify the call came from a legit app build.

---

## Request headers

`client.py` builds the following headers on every call, pulling values from `.env` and fresh tokens from `token_generation.py`:

| Header | Value | Why it matters |
|---|---|---|
| `real-auth-info` | `{userId}!{token}!{deviceUuid}` | Account identity |
| `real-device-uuid` | Per-account UUID from `.env` | Device fingerprint |
| `real-device-name` | e.g. `iPhone15,3` | Device model |
| `real-version` | e.g. `31` | App version |
| `real-device-type` | `ios` | Platform identifier |
| `real-request-token` | Hashids-encoded timestamp | Request obfuscation |
| `real-native-request-token` | HMAC-signed token | Cryptographic request validation |
| `sentry-trace` | `{trace_id}-{span_id}-0` | Sentry tracing — present on every iOS call |
| `baggage` | `sentry-environment=production,...` | Sentry context — present on every iOS call |
| `User-Agent` | `real/1 CFNetwork/{cf} Darwin/{darwin}` | iOS network stack fingerprint |

The `sentry-trace` and `baggage` headers are generated fresh per call with a random `trace_id` (32 hex) and `span_id` (16 hex), matching the pattern the iOS app produces.

---

## Rate limiting

`RateLimitedClient` enforces a minimum gap between any two outbound calls. Three cadence profiles are defined in `client.py`:

| Profile | Range | Use |
|---|---|---|
| `CADENCE_OTD_CLAIM` | 1.5–4.0s | OTD claims — fast taps are realistic in the iOS UI |
| `CADENCE_WRITE` | 2.5–6.0s | Pack buys, boost, marketplace listings |
| `CADENCE_READ` | 4.0–8.5s | Default reads — looks like idle browsing |

Scripts pick their cadence profile at startup and pass it to the client constructor. The gap is enforced by `_wait()`, which checks elapsed time since the last call and sleeps only as long as needed.

---

## Dry-run posture

Every script defaults to dry-run. To actually write to the API you must pass `--live`.

Under the hood: `RateLimitedClient.post()` and `.put()` require `confirm_write=True` or they raise immediately. In dry-run mode, writes are intercepted before they hit the network and a `[DRY-RUN]` line is printed instead. GETs always go through regardless of mode.

This means you can run any script safely without `--live` to verify it would do the right thing.

---

## Daily idempotency

Scripts that perform writes track what they've done today in state files under `state/`:

- `state/bought_{YYYY-MM-DD}.json` — entity IDs bought today
- `state/listed_{YYYY-MM-DD}.json` — card IDs listed today

On each run, the script loads today's state file first. If the entity/card was already acted on, it skips. This means running the same script twice in a day is always safe — the second run is a no-op for anything already done.

---

## OTD claims

OTD (On This Day) claims are historical earnings tied to your passes. There's a daily limit per sport (`claimsRemaining` from the API).

### Step 1 — Fetch today's claims

```bash
python get_claims.py
python get_claims.py --account HDERDAR   # single account
```

This calls `GET /cardhistoricalearnings?day={today}` for each account and saves the response to `claims/{account}_claims_{date}.json`. The claims file is the input for the next step.

### Step 2 — Claim

```bash
python do_claims.py          # dry-run, shows what would be claimed
python do_claims.py --live   # actually PUT each claim
python do_claims.py --account HDERDAR --live
```

The script reads today's claims file, filters out disabled cards (`isDisabled: true`), and PUTs up to `claimsRemaining` cards per sport. It uses the `CADENCE_OTD_CLAIM` timing profile (1.5–4.0s) because rapid claiming of multiple cards is a pattern the iOS app naturally produces.

Each PUT body: `{"userPassId": <id>}`

---

## Pack buying

Daily 200-rax packs are the mechanism for building pass rating. Buying one pack deposits rating into that player's pass directly — no separate "open" step.

### Watchlist

Edit `watchlist_buy.json` to declare which players' packs to auto-buy:

```json
[
  {
    "label": "Shohei Ohtani 2026 MLB",
    "entityId": 660271,
    "sport": "mlb",
    "season": 2026,
    "enabled": true
  }
]
```

`entityId` is the global player ID (same for all users). Set `"enabled": false` to pause a player without removing them from the file.

### Run

```bash
python buy_packs.py                          # dry-run
python buy_packs.py --live                   # actually buy
python buy_packs.py --account HDERDAR --live
```

For each enabled watchlist entry the script:

1. `GET /collectingpacks/player?entityId=X&season=Y&sport=Z` — fetches shop info. If `purchaseDisabledMessage` is set, today's window is already used; skip.
2. Checks `info.cost == 200`. If not 200 rax, skip (price anomaly or pack already bought).
3. `POST /collectingpacks/player` with the confirmed body shape:
   ```json
   {
     "sport": "mlb",
     "season": "2026",
     "cost": 200,
     "acceptPriceChanges": true,
     "entityId": "660271"
   }
   ```
   Note: `season` and `entityId` are strings in the request body.
4. Appends the entity ID to `state/bought_{date}.json`.

---

## Player pass lookup

Before you can populate `watchlist_list.json` you need to find your `cardId` for each pass. That's a per-user value.

```bash
python get_players.py
```

This calls `GET /userpasses/{userId}/passes?entityType=player&season=Y&sport=Z` for each account across all five sports (nhl, nba, mlb, wnba, golf) and saves the results to `players/{account}_{sport}.json`. Browse those files to find the `cardId` for any pass you want to add to the listing watchlist.

---

## Marketplace listing

Once a pass reaches 80 rating (the rare threshold), it's eligible to list.

### Watchlist

Edit `watchlist_list.json`:

```json
[
  {
    "label": "Shohei Ohtani 2026 MLB",
    "cardId": 15331045,
    "entityId": 660271,
    "sport": "mlb",
    "season": 2026,
    "enabled": true
  }
]
```

`cardId` is your per-user pass ID (find it via `get_players.py`). `entityId` is the global player ID needed for price lookup. A player can be on `watchlist_buy.json` without being on `watchlist_list.json` — farming rating and selling are independent opt-ins.

### Run

```bash
python list_pass.py                          # dry-run, shows computed prices
python list_pass.py --live                   # actually post listings
python list_pass.py --account HDERDAR --live
```

For each enabled watchlist entry:

1. `GET /userpasses/{cardId}` — fetches `data.pass.boostValue` (current rating as a float string) and `data.pass.boostInfo.baseRarity` (integer rarity level).
2. If `baseRarity < 3` (not yet rare), skip.
3. Fetch the meowbot recommended price for this `(entityId, season, rating, rarity)` — see Pricing below.
4. Compute prices:
   - `minBidPrice = round_down_tick(meowbot_price × 0.90)`
   - `buyNowPrice = round_up_tick(meowbot_price × 1.10)`
5. `POST /cardmarketplacelistings`:
   ```json
   {
     "listingType": "userpassfull",
     "cardId": 15331045,
     "minBidPrice": 2500,
     "allowBids": true,
     "buyNowPrice": 3500,
     "durationInHours": 72,
     "notificationSettings": { "notifyeverybid": false, "notifytenmin": false }
   }
   ```
6. Appends `cardId` to `state/listed_{date}.json`.

---

## Pricing

### Meowbot (`meowbot.py`)

Prices come from the same data source that powers realapp.tools. The script posts to a Supabase endpoint:

```
POST https://mfsyhtuqybbxprgwwykd.supabase.co/functions/v1/market-data
{"action": "get_play_card_market_summary", "payload": {"entityId": N, "season": Y}}
```

The response contains a `bulk.byRarity` array. For each rarity tier the key field is `twAvgRr` — the time-weighted average rax-per-rating. This is the "Recommended R/R" number shown on the realapp.tools player page.

Recommended price for a pass = `pass_rating × twAvgRr`

If a rarity tier has fewer than 20 samples, `recommended_price_for_pass()` returns `None` and the listing is skipped (not enough market data to trust the price).

Rarity integers: 3 = Rare, 4 = Epic, 5 = Legendary, 6 = Mystic, 7 = Iconic.

### Tick rounding (`pricing.py`)

The Real mobile listing UI restricts prices to a discrete set of valid values:

| Price range | Tick size |
|---|---|
| Below 2000 rax | 100 rax |
| 2000 rax and above | 500 rax |

`round_up_tick()` rounds the buy-now price up to the nearest valid tick.
`round_down_tick()` rounds the starting bid down to the nearest valid tick.

Both functions handle the 2000-rax boundary — prices that would cross the boundary when rounded snap to exactly 2000.

---

## Boost

`boost.py` applies a stat booster to each player pass for a given sport. It picks a random stat key from `[1, 2, 3, 4, 5, 21]` (PTS, AST, REB, STL, BLK, 3PM) and PUTs to `/userpassboostercards/{id}/rarity/{rarity}`.

**The boost endpoint is currently broken upstream.** The script is ready but will return 4xx/5xx until your friend ships the server fix.

```bash
python boost.py --account HDERDAR --sport nba          # dry-run
python boost.py --account HDERDAR --sport nba --live   # actually boost
```

Requires that `players/{account}_{sport}.json` exists — run `get_players.py` first.

Results are saved to `boosts/{account}_{sport}_boosts.json`.

---

## Detection risk posture

The following changes from the original codebase eliminate the clearest fingerprint mismatches:

- **Sentry headers** — `sentry-trace` and `baggage` are now on every request. The iOS app sends these on every call; their absence was a binary tell.
- **`real-native-request-token`** — was missing from some scripts in the original; now always included via the shared client.
- **Device fingerprint** — `User-Agent`, `real-version`, and `real-device-uuid` are configurable per-account in `.env`. They are not hardcoded.
- **Request timing** — all calls go through `RateLimitedClient`. Zero-gap burst patterns (10 PUTs in under 1 second) are eliminated.

Remaining open items:
- Daily run time should be randomized across a morning window (07:00–09:30) — solved by the orchestrator when built.
- Listing duration is hardcoded to 72h — need to capture alternative durations from the app first.
- Boost stat selection is uniform-random — a weighted or per-player-preferred stat would be more realistic.

---

## What's still uncaptured

These API details are confirmed missing. Nothing that depends on them can ship until they're captured via ProxyPin.

1. **3rd OTD bet** — endpoint path and body shape unknown. Blocks morning ritual step 3.
2. **Real Pro account flag** — which field on which endpoint tells us the account has Pro access. Blocks gating the bet.
3. **Listing duration alternatives** — the app offers other durations besides 72h. Capture one alternative and the orchestrator can randomize.
4. **`POST /cardmarketplacelistings/{id}/bid`** — body shape assumed `{"bidAmount": N}` but not confirmed. Blocks the player pass scanner.
5. **Listings GET pagination** — params for paging through open marketplace listings. Blocks the scanner.
6. **"Top bid is mine" field** — need to know which field on a listing object indicates the current top bid is from the authenticated user. Blocks self-overbid protection in the scanner.

---

## What's not built yet

- **Daily orchestrator** — randomized morning start, sequences buy → claim → list with extra inter-step delay. This is the next build priority.
- **Player pass scanner** — browse marketplace listings, score deals against meowbot price (`deal_score = (meowbot_rec - top_bid) / meowbot_rec`), bid on qualifying listings. Full spec in `Project_vision.md`. Build priority 2, after morning ritual is reliable.

---

## File reference

| File | Purpose |
|---|---|
| `client.py` | Shared HTTP client — headers, timing, dry-run gate |
| `token_generation.py` | Native request token + Hashids request token |
| `accounts.py` | AccountFingerprint objects from `.env` |
| `get_claims.py` | Fetch today's OTD claim list |
| `do_claims.py` | PUT each claimable OTD card |
| `get_players.py` | Fetch pass list per sport (finds cardId values) |
| `buy_packs.py` | Buy daily 200-rax packs from watchlist_buy.json |
| `list_pass.py` | List rare passes from watchlist_list.json |
| `meowbot.py` | Supabase market-data price lookup |
| `pricing.py` | Tick rounding for marketplace prices |
| `boost.py` | Apply stat boosters (endpoint broken — ready when fixed) |
| `watchlist_buy.json` | Players whose daily packs to buy |
| `watchlist_list.json` | Passes to list once they hit rare |
| `state/` | Daily idempotency state files |
| `claims/` | Daily OTD claim JSON snapshots (gitignored) |
| `players/` | Pass list snapshots per account/sport |
| `Project_vision.md` | Full spec: end state, domain model, build sequence |
| `RED_FLAGS.md` | Detection risk inventory with status of each item |
| `CLAUDE.md` | Project status snapshot — what works, what's open |
