# GUI setup

A Streamlit dashboard for the daily ritual. v1 covers buy packs, claim OTD,
list eligible passes, and a "run all" shortcut.

## One-time install

```bash
cd ~/Documents/Claude\ Projects/n3w\ opt1mis3r/opt1mis3r.btc-master
source venv/bin/activate    # if you have a venv
pip install -r requirements.txt
```

That installs `streamlit` alongside the existing deps.

## Launch

```bash
./run_gui.sh
```

Streamlit will print a URL like `http://localhost:8501` — open it in your
browser. The terminal that ran `run_gui.sh` will keep printing log lines; leave
it running while you use the dashboard.

To stop: `Ctrl-C` in that terminal.

## What's in v1

- **Sidebar** — account picker, live/dry-run toggle (defaults to dry-run).
- **Top status row** — today's metrics: packs bought, OTD claimable, passes
  listed, mode indicator.
- **Action buttons**:
  - 🎁 Buy packs → runs `buy_packs.py --account X [--live]`
  - 💰 Claim OTD → runs `get_claims.py` then `do_claims.py`
  - 📤 List eligible passes → runs `list_pass.py`
  - 🌅 Run all → all three in sequence
- **Live log stream** below each button — every line the script prints shows
  up in real time.
- **Watchlist viewer** — read-only display of `watchlist_buy.json` and
  `watchlist_list.json`. Edit those files by hand and reload.

## Safety posture preserved

The GUI doesn't bypass anything we built into the CLI scripts:
- Dry-run is still the default
- Rate-limiting and sentry-headers still active
- Daily idempotency state files still gate writes
- The "Live" toggle in the sidebar maps to `--live` in the subprocess args

## What's not here (yet)

- Watchlist editing UI (edit JSON files for now)
- Scheduled / unattended runs (use `launchd` for that, separate workstream)
- Boost button (waiting on friend's endpoint fix)
- Player pass scanner / auto-bidder (future workstream — see Project_vision.md)
- Historical run log / charts

## Troubleshooting

- **"No accounts found" error** → `.env` is missing `ACCOUNTS=HDERDAR` (or
  similar). Set it and reload.
- **All actions exit non-zero with auth errors** → recapture your iPhone's
  `real-auth-info` via ProxyPin and update `.env`.
- **Streamlit shows a stale state row** → reload the page after a successful
  run; state files update on disk but the UI caches the snapshot from page-load.
