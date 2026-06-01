"""
app.py — basic Streamlit dashboard for opt1mis3r.

Launch:
    streamlit run app.py

What's here in v1:
  * Account picker + live/dry-run toggle (sidebar)
  * Today's state panel (what's already been done)
  * Action buttons:
      - Buy daily packs
      - Claim OTD  (runs get_claims then do_claims)
      - List eligible passes
      - Run all (the morning ritual, sequenced)
  * Streaming log output

Each action shells out to the existing CLI scripts via subprocess so the GUI
inherits all the dry-run + rate-limit + sentry-header protections we already
built — no logic duplication.
"""
from __future__ import annotations

import json
import subprocess
import sys
from datetime import date
from pathlib import Path

import streamlit as st

from accounts import list_account_names

PROJECT_ROOT = Path(__file__).resolve().parent
STATE_DIR = PROJECT_ROOT / "state"
CLAIMS_DIR = PROJECT_ROOT / "claims"
TODAY = date.today().isoformat()


# ─── PAGE CONFIG ───────────────────────────────────────────────────────────────
st.set_page_config(page_title="opt1mis3r", page_icon="🎯", layout="wide")
st.title("opt1mis3r — daily ritual")
st.caption(f"{TODAY}  ·  Local automation cockpit for Real Sports")


# ─── SIDEBAR ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.header("Run config")

    accounts = list_account_names()
    if not accounts:
        st.error("No accounts found. Set `ACCOUNTS=…` in `.env`.")
        st.stop()

    account = st.selectbox("Account", accounts, index=0)
    live = st.toggle(
        "Live mode",
        value=False,
        help="When OFF: dry-run — prints intended requests, makes no writes. "
             "When ON: actually mutates real.vg.",
    )
    if live:
        st.warning("⚠️ LIVE — writes will hit api.real.vg")
    else:
        st.success("✅ Dry-run — safe to click anything")

    st.divider()
    st.caption(
        "Tip: stay in dry-run until you've reviewed today's log at least once. "
        "Once a script reports `[+]` lines that look right, flip the toggle."
    )


# ─── STATE PANEL ───────────────────────────────────────────────────────────────
def _read_json(p: Path) -> dict | list | None:
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text())
    except json.JSONDecodeError:
        return None


bought_state = _read_json(STATE_DIR / f"bought_{TODAY}.json") or {"bought_entity_ids": []}
listed_state = _read_json(STATE_DIR / f"listed_{TODAY}.json") or {"listed_card_ids": []}
claims_data  = _read_json(CLAIMS_DIR / f"{account}_claims_{TODAY}.json")

claimable_count = 0
if claims_data and isinstance(claims_data, dict):
    for sport in claims_data.get("sportEarnings", []):
        for pe in sport.get("passEarnings", []):
            if not pe.get("isDisabled", False):
                claimable_count += 1

col_a, col_b, col_c, col_d = st.columns(4)
col_a.metric("Packs bought today", len(bought_state["bought_entity_ids"]))
col_b.metric("Claimable OTD cards", claimable_count if claims_data else "?",
             help="? means you haven't fetched claims yet today.")
col_c.metric("Passes listed today", len(listed_state["listed_card_ids"]))
col_d.metric("Mode", "LIVE" if live else "DRY-RUN")


# ─── ACTION RUNNERS ────────────────────────────────────────────────────────────
def _run_streaming(label: str, args: list[str]) -> int:
    """Run a subprocess in PROJECT_ROOT, stream stdout to the page."""
    with st.expander(f"▶ {label}", expanded=True):
        st.code(" ".join(args), language="bash")
        ph = st.empty()
        log_lines: list[str] = []
        proc = subprocess.Popen(
            args,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            cwd=str(PROJECT_ROOT),
        )
        for line in proc.stdout:                       # type: ignore[union-attr]
            log_lines.append(line.rstrip())
            ph.code("\n".join(log_lines), language="text")
        proc.wait()
        if proc.returncode != 0:
            st.error(f"{label} exited with code {proc.returncode}")
        else:
            st.success(f"{label} done")
        return proc.returncode


def _args_for(script: str) -> list[str]:
    args = [sys.executable, script, "--account", account]
    if live:
        args.append("--live")
    return args


def action_buy() -> None:
    _run_streaming("Buy daily packs", _args_for("buy_packs.py"))


def action_otd() -> None:
    """Two-step: first GET the day's claims, then PUT each claim."""
    rc = _run_streaming("Fetch today's claims", [sys.executable, "get_claims.py", "--account", account])
    if rc == 0:
        _run_streaming("Claim OTD", _args_for("do_claims.py"))


def action_list() -> None:
    _run_streaming("List eligible passes", _args_for("list_pass.py"))


def action_all() -> None:
    action_buy()
    action_otd()
    action_list()


# ─── ACTION BUTTONS ────────────────────────────────────────────────────────────
st.header("Actions")
b1, b2, b3, b4 = st.columns(4)
clicked = None
if b1.button("🎁 Buy packs", use_container_width=True): clicked = action_buy
if b2.button("💰 Claim OTD", use_container_width=True): clicked = action_otd
if b3.button("📤 List eligible passes", use_container_width=True): clicked = action_list
if b4.button("🌅 Run all (morning ritual)", use_container_width=True, type="primary"): clicked = action_all

if clicked is not None:
    clicked()


# ─── WATCHLIST VIEW (read-only for v1) ─────────────────────────────────────────
st.header("Watchlists")
wcol1, wcol2 = st.columns(2)
with wcol1:
    st.subheader("Buy")
    buy_wl = _read_json(PROJECT_ROOT / "watchlist_buy.json") or []
    if buy_wl:
        st.json(buy_wl, expanded=False)
    else:
        st.info("Empty.")
with wcol2:
    st.subheader("List")
    list_wl = _read_json(PROJECT_ROOT / "watchlist_list.json") or []
    if list_wl:
        st.json(list_wl, expanded=False)
    else:
        st.info("Empty.")

st.caption("Edit watchlists by hand in `watchlist_buy.json` / `watchlist_list.json` then reload this page.")
