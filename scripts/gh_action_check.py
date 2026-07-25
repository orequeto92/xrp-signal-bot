#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Runs once, checks the market, and pushes a Telegram message ONLY when a fresh
high-conviction setup appears. Meant to run on a schedule via GitHub Actions
(no server needed) — see .github/workflows/alerts.yml.

Reads secrets from environment variables (set as GitHub Actions repo secrets):
  TELEGRAM_TOKEN, TELEGRAM_CHAT_ID, BALANCE_COINS

State (the last alert's signature, to avoid re-alerting the same setup) is
kept in a small JSON file restored/saved by actions/cache between runs.
"""
import sys, os, json, urllib.request, urllib.parse, urllib.error

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from engine import signal
from engine.format import describe

# --- config: secrets required, the rest has sensible defaults ---
TOKEN = os.environ.get("TELEGRAM_TOKEN")
CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")
BALANCE_COINS = float(os.environ.get("BALANCE_COINS", "0") or 0)

SYMBOL = os.environ.get("SYMBOL", "XRPUSDT")
TRADE_PAIR = os.environ.get("TRADE_PAIR", "XRPUSD")
DIRECTOR_SYMBOL = os.environ.get("DIRECTOR_SYMBOL", "BTCUSDT")
RISK_PCT = float(os.environ.get("RISK_PCT", "2.0"))
LEV_MAX = int(os.environ.get("LEV_MAX", "10"))
SL_MIN_PCT = float(os.environ.get("SL_MIN_PCT", "1.5"))
SL_MAX_PCT = float(os.environ.get("SL_MAX_PCT", "4.0"))
ALERT_MIN_SCORE = int(os.environ.get("ALERT_MIN_SCORE", "7"))

STATE_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                          ".cache", "alert_state.json")


class Cfg:
    """A tiny stand-in for config.py, built from env vars, for engine.signal."""
    DIRECTOR_SYMBOL = DIRECTOR_SYMBOL
    RISK_PCT = RISK_PCT
    LEV_MAX = LEV_MAX
    SL_MIN_PCT = SL_MIN_PCT
    SL_MAX_PCT = SL_MAX_PCT


def load_state():
    try:
        return json.load(open(STATE_PATH, encoding="utf-8"))
    except Exception:
        return {"last_alert_sig": None}


def save_state(s):
    os.makedirs(os.path.dirname(STATE_PATH), exist_ok=True)
    json.dump(s, open(STATE_PATH, "w", encoding="utf-8"))


def send_telegram(text):
    url = "https://api.telegram.org/bot%s/sendMessage" % TOKEN
    data = urllib.parse.urlencode({"chat_id": CHAT_ID, "text": text}).encode()
    req = urllib.request.Request(url, data=data, headers={"User-Agent": "xrp-signal-bot"})
    try:
        urllib.request.urlopen(req, timeout=30).read()
    except urllib.error.HTTPError as e:
        # Surface Telegram's actual error reason (e.g. chat not found, bot blocked,
        # user never messaged the bot) instead of a bare "HTTP 400".
        body = e.read().decode(errors="replace")
        print("Telegram API rejected the message:", body)
        raise


def main():
    if not TOKEN or not CHAT_ID:
        sys.exit("Missing TELEGRAM_TOKEN / TELEGRAM_CHAT_ID secrets.")

    d = signal.evaluate(SYMBOL, BALANCE_COINS, Cfg)
    state = load_state()

    actionable = d.get("decision") == "TRADE" and d.get("score", 0) >= ALERT_MIN_SCORE
    sig = ("%s-%s-%d" % (d.get("side"), d.get("grade"), d.get("score"))) if actionable else None

    if sig and sig != state.get("last_alert_sig"):
        msg = "🔔 OPORTUNIDAD en %s\n\n%s" % (TRADE_PAIR, describe(d, SYMBOL, TRADE_PAIR, RISK_PCT))
        send_telegram(msg)
        print("Alert sent:", sig)
    else:
        print("No new alert. decision=%s score=%s" % (d.get("decision"), d.get("score")))

    if state.get("last_alert_sig") != sig:
        state["last_alert_sig"] = sig
        save_state(state)


if __name__ == "__main__":
    main()
