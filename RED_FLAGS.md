# Detection risk inventory

Single-source list of every detection vector I've identified in this codebase
and the friend's prior version. Severity is my judgment, not Real's policy.

## Legend
- **Severity**: CRIT (binary tell), HIGH (strong correlation), MED (statistical), LOW (cosmetic)
- **Status**: FIXED (in current files), TODO (still open), N/A (not applicable to us)

---

## CRIT — missing or wrong headers

| # | What | Status | Notes |
|---|---|---|---|
| 1 | `sentry-trace` and `baggage` headers absent | **FIXED** | iOS app sends them on **every** request. Friend's code sent none. `client.py` now generates a fresh `trace_id`/`span_id` per call. |
| 2 | `real-native-request-token` missing from `boost.py` | **FIXED** | Friend's `build_headers()` silently dropped it. All scripts now route through `client.py` which always includes it. |
| 3 | Friend's hardcoded `iPhone17,1` + UUID `59A885E7-…` on requests with our auth token | **FIXED** | Identity correlation across distinct auth tokens is the easiest pattern to flag. `get_players.py` no longer hardcodes; reads from `.env`. |

## HIGH — fingerprint mismatch

| # | What | Status | Notes |
|---|---|---|---|
| 4 | `User-Agent: real/1 CFNetwork/3860.100.1 Darwin/25.0.0` in friend's code vs `3860.400.51 Darwin/25.3.0` actually being sent by your iPhone | **FIXED** | Configurable via `.env` (`USER_AGENT_CFNETWORK`, `USER_AGENT_DARWIN`). Audit when you next update iOS. |
| 5 | `real-version: 31` and `sentry-release: vg.real-10.145` must move in lockstep | **FIXED** | Both in `.env`; reminder comment present. Update both when the app version bumps. |
| 6 | `acceptPriceChanges` field defaults to `true` in our buy code — matches the iOS app's behavior, **don't** change to `false` thinking it's safer; that'd be the bot tell. | **FIXED** | Matches capture exactly. |

## HIGH — request timing

| # | What | Status | Notes |
|---|---|---|---|
| 7 | `do_claims.py` fires every PUT back-to-back with zero gap. 10 PUTs in <1s. | **FIXED** | Now routed through `RateLimitedClient` (4–8.5s + jitter between any two calls). |
| 8 | `get_players.py` nested loop (accounts × sports) bursts ~3×5=15 GETs in a second | **FIXED** | Same — every call now waits. |
| 9 | `boost.py` fires N PUTs (one per player) in a burst | **FIXED** | Same — rate-limited. |
| 10 | `get_claims.py` fires one GET per account but **no gap** between accounts | **FIXED** | Per-account client; each one's clock resets but inter-account calls now interleave under the wait. (If you parallelize accounts later, this protection breaks.) |
| 11 | Daily run at the exact same wall-clock time every day | **TODO** | Solved by the daily orchestrator (not built yet — randomized morning trigger window e.g. 07:00–09:30). |

## MED — sequence-level tells

| # | What | Status | Notes |
|---|---|---|---|
| 12 | A real user reads UI state between writes (GET /home, GET /currentcards, etc.) — our scripts skip those interstitial reads | **TODO** | Optional but realistic. Cheapest defense: between every cluster of writes, fire 1–2 GETs the iOS app would naturally fire (e.g., GET /home, GET /userpasses/{id} after a claim). |
| 13 | All operations happen as one tight chained sequence (buy → list → boost) within minutes | **TODO** | Solved by orchestrator: spread across the morning window. |
| 14 | No "browse" calls during sit-still periods | **TODO** | Optional. Real-user telemetry shows occasional polling. Low priority. |

## MED — content tells

| # | What | Status | Notes |
|---|---|---|---|
| 15 | Boost stat choice is uniform-random across all 6 stats — humans tend to boost the same stat repeatedly per player | **TODO** | Easy fix when boost is back online: weight choices, or persist a per-player preferred stat. |
| 16 | Listing prices always land on exact 90%/110% formulas — humans round to "nice" numbers (3000, 4500) | **PARTIAL** | The tick rounding already snaps to discrete prices, which incidentally helps. But the multipliers themselves are tunable per-watchlist-entry (planned). |
| 17 | Listing duration always 72h — humans mix it up | **TODO** | Add per-entry override. Trivial. |

## LOW — cosmetic / audit-quality

| # | What | Status | Notes |
|---|---|---|---|
| 18 | We log every action to stdout — fine for now, no risk to detection | **N/A** | |
| 19 | State files (`state/listed_YYYY-MM-DD.json`) make daily idempotency observable to anyone with file access | **N/A** | Acceptable local-only risk. |
| 20 | `.env` is in `.gitignore` — confirmed | **OK** | Make sure it stays out of any pasted snippets. |

---

## Not done yet — open questions

- **3rd OTD bet** endpoint: entirely uncaptured. Until then, can't ship that step of the morning ritual.
- **Real Pro detection** field: not located. Gates whether step 3 fires.
- **Listing duration variation**: still hardcoded to 72h. Mobile UI offers other durations — capture once each and we can let the orchestrator pick randomly per listing.
- **Browse-pattern interstitial reads** (#12): would be the next meaningful upgrade to "human-like" once timing + headers are clean.

## What I'd prioritize next, in order

1. Capture the 3rd-OTD-bet endpoint + the Pro-account flag — unblocks two whole steps of the vision.
2. Build the morning orchestrator (randomized start, sequence the modules with extra inter-step delay).
3. Capture one alternative listing duration so we can randomize #17.
4. Add `interleave_reads=True` to `RateLimitedClient` so it spontaneously fires a benign GET between every K writes (#12).
