# Project vision

## The end state

A single agent that wakes at a **randomized morning time** and runs this sequence
end-to-end with human-like API pacing:

1. **Buy declared player packs.** For each player on the auto-buy watchlist,
   buy that player's 200-rax daily pack. (Real packs auto-deposit rating into
   the pass — there's no separate "open" step.)
2. **Claim OTD.** Run the historical-earnings claim sweep across all sports.
3. **3rd OTD bet** — only if the account has Real Pro. Place the bet on the
   third claim.
4. **Pass-rarity listing.** For every pass on the **auto-list watchlist** that
   has just crossed 80 rating (rare), look up meowbot's bulk price at
   <https://realapp.tools/> and list the pass on the Real marketplace.
5. **Boost.** Apply boosters to all relevant cards. (Boost endpoint is
   currently broken — gated until friend ships fix.)

Everything runs **once per day**. No re-runs. No retries that look like a bot.

---

## Core domain model

- **Pass** — a player-bound container that accumulates **rating** as you buy
  that player's packs. Rating starts at 0 and climbs ~10–15 per pack, so
  reaching **80 (rare)** takes ~6–8 consecutive days of pack-buying.
- **Pack (player pack, 200 rax)** — the daily cheap pack per player. Buying
  one deposits rating directly into the pass; there is no separate open step.
- **OTD claim** — daily historical earnings sweep, already shipping.
- **3rd OTD bet** — extra bet only available to Real Pro accounts.
- **Rarity gate** — `pass.rating >= 80` ≡ rare. Triggers listing if and only
  if the pass is on the auto-list watchlist.

---

## Two explicit watchlists

Auto-anything is **opt-in per pass**. The agent never lists or buys for a
pass that wasn't explicitly declared.

### `watchlist_buy.json`
Players whose daily 200-rax pack we should buy.
```json
[
  { "label": "Shohei Ohtani 2026 MLB", "entityId": 660271, "sport": "mlb", "season": 2026 }
]
```

### `watchlist_list.json`
Passes that should auto-list when their rating crosses 80. Often the same set
as buy, but not always — e.g. you might farm a pass without ever wanting to
sell it.
```json
[
  { "label": "Shohei Ohtani 2026 MLB", "cardId": 15331045, "sport": "mlb", "season": 2026 }
]
```

The `cardId` for a pass is per-user; it has to be looked up once via
`get_players.py` and pasted in. `entityId` is the player and is global.

---

## Listing rules (confirmed from your captures)

- **Endpoint**: `POST /cardmarketplacelistings`
- **Body shape**:
  ```json
  {
    "listingType": "userpassfull",
    "cardId": <pass cardId>,
    "minBidPrice": <starting bid>,
    "allowBids": true,
    "buyNowPrice": <buy-now / "target">,
    "durationInHours": 72,
    "notificationSettings": { "notifyeverybid": false, "notifytenmin": false }
  }
  ```
- **Price math**:
  - `buyNowPrice  ≈ meowbot_price * 1.10` (rounded up to nearest valid tick)
  - `minBidPrice  ≈ meowbot_price * 0.90` (rounded down to nearest valid tick)
- **Valid price ticks** (mobile listing UI constraints):
  - 1000–2000 rax → increments of 100
  - 2000+ rax → increments of 500
  - Below 1000 → assume increments of 100 unless captures prove otherwise
- **Discrepancy to resolve**: the captured body has `durationInHours: 72`
  (3 days), but the spec mentioned a "10-minute auction". Treat 72h as the
  current truth until clarified.

---

## Pack-buy flow (confirmed)

For a watchlist entry `{entityId, sport, season}`:

1. `GET /collectingpacks/player?entityId=X&season=Y&sport=Z` — returns the
   pack's price.
2. **If price == 200**: `POST /collectingpacks/player` with the body
   describing the pack. ← **Body shape still uncaptured** — `Content-Length: 88`
   from the HAR but contents not yet pasted.
3. `GET /userpasses/<cardId>` — confirm the pass now reflects the new rating.
4. If the new rating crossed 80 **and** this `cardId` is on
   `watchlist_list.json`, trigger the listing flow.

---

## Hard rules

- **Human-like timing.** Randomized morning trigger (not 07:00:00 sharp), 4s
  floor + uniform jitter to ~8s between any two outbound API calls; full
  sequence spread over enough wall-clock time that it doesn't look bursty.
- **Posture: read-by-default, write-opt-in.** Every write requires an
  explicit confirm flag or the script refuses.
- **Idempotency per day.** Daily state file gates every write — second run
  same day is a no-op.
- **Local on the user's Mac.** No cloud, no shared infra. Non-technical
  operator should be able to start/stop it.

---

## Player pass scanner (added 2026-05-19)

A parallel workstream from the main morning ritual: continuously (or on a
randomized schedule) scan the marketplace for **undervalued** player full-pass
listings and bid on the ones that look like deals — same logic realapp.tools
shows in its public "Deal Score" UI.

### Flow
1. `GET /cardmarketplacelistings?listingType=userpassfull&...` — page through
   open player-pass listings. (Path is confirmed in original captures; pagination
   params still uncaptured.)
2. For each listing, fetch the meowbot recommended price for that
   `(entityId, season, rarity)` via the supabase market-data endpoint we
   already wired in `meowbot.py`.
3. Compute deal score = `(meowbot_recommended - current_top_bid) / meowbot_recommended`.
4. If deal score > `MIN_DEAL_SCORE` **and** the entry passes other filters
   (sport, rarity floor, daily spend cap, watchlist), place a bid via
   `POST /cardmarketplacelistings/{id}/bid` body `{"bidAmount": N}`.

### Bid-amount rule (proposed — confirm before building)
`bidAmount = min(meowbot_recommended * MAX_BID_FRACTION, current_top_bid + tick)`
where `MAX_BID_FRACTION` defaults to ~0.70 (don't pay >70% of meowbot's
recommended price) and `tick` respects the same 100/500 increments used for
listing.

### Hard rules (must be in code before live)
- **Daily spend cap** — `DAILY_BID_BUDGET_RAX` ceiling that survives across
  restarts; the scanner refuses to bid once it's blown.
- **Per-listing idempotency** — never bid twice on the same listing-id in one
  day even if a re-scan would otherwise qualify.
- **Don't outbid yourself** — if the current top bid is already ours, skip.
- **Watchlist filter** (optional but recommended) — allow restricting to a
  declared set of `entityId`s or sports, same opt-in posture as buy/list.
- **Cadence** — `CADENCE_WRITE` for the bid POSTs; reads can run at
  `CADENCE_READ`. Continuous polling is *not* allowed; do at most N scans/day
  at randomized intervals.

### Still uncaptured for this
1. `POST /cardmarketplacelistings/{id}/bid` body shape (`{"bidAmount":N}`
   assumed but not confirmed).
2. Pagination params on the listings GET.
3. How to detect "this top bid is mine" — likely a field on the listing
   object, capture once.

### Risks specific to this feature
- **Highest-spend feature so far.** Bid errors cost real rax. Mandatory dry-run
  default, mandatory `confirm_write=True`, mandatory daily cap.
- **Most bot-shaped behavior** — periodic marketplace scans are the prototypical
  trader-bot pattern. Cadence + randomized timing here matter more than
  anywhere else.
- **Worth doing only after** the morning ritual is shipping reliably; this
  is a second priority, not first.

---

## Out of scope for v1

- ~~Buying anything from the marketplace~~ (now in scope per scanner spec above).
- Multi-account orchestration (single-account first).
- Auto-relisting cancelled or expired listings.
- Auto-boost (waiting on friend's fix).
- Any web dashboard or push notifications (logs to disk only).

---

## What's still uncaptured

1. **POST `/collectingpacks/player` body** — only `Content-Length: 88` known.
2. **3rd OTD bet endpoint** — entirely uncaptured.
3. **Real Pro account flag** — which field on which endpoint tells us the
   account has Pro? Determines whether step 3 fires.
4. **Auction-duration mode** — 72h vs the mentioned "10 minute auction".

---

## Sequencing the build

1. Listing module *(buildable today — endpoint + body confirmed)*
2. Pack-buy module *(blocked on the one missing body capture)*
3. Combined buy → list pipeline with watchlists
4. Daily orchestrator with randomized morning start
5. 3rd OTD bet (after endpoint capture)
6. Auto-boost (after friend's fix lands)
7. Pro-account detection + gating
