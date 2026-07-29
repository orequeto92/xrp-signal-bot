# -*- coding: utf-8 -*-
"""Loads params.json — the single source of truth for strategy parameters.

The same file is read by the local bot, the GitHub Actions runner and the mobile
app, so a change in one place applies everywhere. Secrets (Telegram token, chat
id) and the account balance are deliberately NOT here: this repo is public.

Values are flattened from their sections, so `load()["RISK_PCT"]` works
regardless of which group a key lives in.
"""
import os, json

PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "params.json")

# Fallbacks if params.json is missing or a key was removed — the system must
# still run with sane values rather than crash.
DEFAULTS = {
    "SYMBOL": "XRPUSDT", "TRADE_PAIR": "XRPUSD", "DIRECTOR_SYMBOL": "BTCUSDT",
    "RISK_PCT": 2.0, "RISK_PCT_HIGH": 3.0, "SCORE_RISK_ALTO": 9, "LEV_MAX": 10,
    "SL_MIN_PCT": 1.5, "SL_MAX_PCT": 4.0, "ATR_STOP_MULT": 2.5,
    "DAILY_BLOCK_LOW": 30, "DAILY_BLOCK_HIGH": 70,
    "PROACTIVE_ALERTS": True, "ALERT_MIN_SCORE": 7,
    "CHECK_INTERVAL_MIN": 20, "ALERT_HOURS_UTC": (12, 5),
}


def load(path=None):
    """Return a flat dict of parameters, defaults filled in for anything missing."""
    out = dict(DEFAULTS)
    try:
        raw = json.load(open(path or PATH, encoding="utf-8"))
    except Exception:
        return out
    for key, value in raw.items():
        if key.startswith("_"):
            continue
        if isinstance(value, dict):          # a section: flatten it
            out.update(value)
        else:
            out[key] = value
    if isinstance(out.get("ALERT_HOURS_UTC"), list):
        out["ALERT_HOURS_UTC"] = tuple(out["ALERT_HOURS_UTC"])
    return out


def apply_to(obj, path=None):
    """Set every parameter as an attribute on `obj` (a config module or class)."""
    for key, value in load(path).items():
        setattr(obj, key, value)
    return obj
