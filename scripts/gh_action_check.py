#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
One-shot runner for GitHub Actions (no server needed). On each scheduled run it:

  1. Answers any pending Telegram commands (/oportunidades, /saldo, /estado...).
  2. Pushes an alert if a fresh high-conviction setup appeared.

Replies are therefore NOT instant: they arrive on the next scheduled run. Run
bot.py locally when you want immediate answers.

Secrets come from environment variables (set as GitHub Actions repo secrets):
  TELEGRAM_TOKEN, TELEGRAM_CHAT_ID, BALANCE_COINS

State (balance, trade log, last alert signature) is kept in a small JSON file
restored/saved by actions/cache between runs. Cache is best-effort: if it is
evicted, the balance falls back to the BALANCE_COINS secret.
"""
import sys, os, json, time, urllib.request, urllib.parse, urllib.error

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from engine import signal, commands
from engine.format import describe

# --- config: secrets required, the rest has sensible defaults ---
TOKEN = os.environ.get("TELEGRAM_TOKEN")
CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")
BALANCE_COINS = float(os.environ.get("BALANCE_COINS", "0") or 0)

ALERT_MIN_SCORE = int(os.environ.get("ALERT_MIN_SCORE", "7"))

STATE_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                          ".cache", "state.json")


class Cfg:
    """Stand-in for config.py, built from env vars, for engine.signal/commands."""
    SYMBOL = os.environ.get("SYMBOL", "XRPUSDT")
    TRADE_PAIR = os.environ.get("TRADE_PAIR", "XRPUSD")
    DIRECTOR_SYMBOL = os.environ.get("DIRECTOR_SYMBOL", "BTCUSDT")
    RISK_PCT = float(os.environ.get("RISK_PCT", "2.0"))
    LEV_MAX = int(os.environ.get("LEV_MAX", "10"))
    SL_MIN_PCT = float(os.environ.get("SL_MIN_PCT", "1.5"))
    SL_MAX_PCT = float(os.environ.get("SL_MAX_PCT", "4.0"))


def load_state():
    try:
        s = json.load(open(STATE_PATH, encoding="utf-8"))
    except Exception:
        s = {}
    s.setdefault("balance_coins", BALANCE_COINS)
    s.setdefault("initial_coins", BALANCE_COINS)
    s.setdefault("trades", [])
    s.setdefault("last_alert_sig", None)
    return s


def save_state(s):
    os.makedirs(os.path.dirname(STATE_PATH), exist_ok=True)
    json.dump(s, open(STATE_PATH, "w", encoding="utf-8"), indent=1, ensure_ascii=False)


# ---------- telegram ----------
def tg(method, params, timeout=30):
    url = "https://api.telegram.org/bot%s/%s" % (TOKEN, method)
    data = urllib.parse.urlencode(params).encode()
    req = urllib.request.Request(url, data=data, headers={"User-Agent": "xrp-signal-bot"})
    try:
        return json.load(urllib.request.urlopen(req, timeout=timeout))
    except urllib.error.HTTPError as e:
        # Surface Telegram's actual reason (chat not found, bot blocked, ...).
        print("Telegram API error on %s: %s" % (method, e.read().decode(errors="replace")))
        raise


def send(text):
    tg("sendMessage", {"chat_id": CHAT_ID, "text": text})


def answer_commands(state):
    """Reply to any pending commands, then acknowledge them server-side.

    Telegram queues updates for ~24h; passing offset=last+1 confirms them so the
    next run does not see them again. That keeps command handling correct even
    if the cache between runs is lost.
    """
    resp = tg("getUpdates", {"timeout": 0})
    updates = (resp or {}).get("result") or []
    if not updates:
        return False

    changed = False
    last_id = updates[-1]["update_id"]
    for u in updates:
        msg = u.get("message") or u.get("edited_message")
        if not msg or "text" not in msg:
            continue
        if str(msg["chat"]["id"]) != str(CHAT_ID):
            continue                      # ignore everyone but the owner
        try:
            reply, state_changed = commands.handle(msg["text"], state, Cfg)
            changed = changed or state_changed
        except Exception as e:
            reply = "Error procesando el comando: %s" % e
        send(reply)
        print("Answered:", msg["text"][:40])

    tg("getUpdates", {"offset": last_id + 1, "timeout": 0})   # acknowledge
    return changed


def alert_check(state):
    """Send an alert only when a fresh high-conviction setup shows up."""
    d = signal.evaluate(Cfg.SYMBOL, state["balance_coins"], Cfg)
    actionable = d.get("decision") == "TRADE" and d.get("score", 0) >= ALERT_MIN_SCORE
    sig = ("%s-%s-%d" % (d.get("side"), d.get("grade"), d.get("score"))) if actionable else None

    if sig and sig != state.get("last_alert_sig"):
        send("🔔 OPORTUNIDAD en %s\n\n%s"
             % (Cfg.TRADE_PAIR, describe(d, Cfg.SYMBOL, Cfg.TRADE_PAIR, Cfg.RISK_PCT)))
        print("Alert sent:", sig)
    else:
        print("No new alert. decision=%s score=%s" % (d.get("decision"), d.get("score")))

    if state.get("last_alert_sig") != sig:
        state["last_alert_sig"] = sig
        return True
    return False


def main():
    if not TOKEN or not CHAT_ID:
        sys.exit("Missing TELEGRAM_TOKEN / TELEGRAM_CHAT_ID secrets.")

    state = load_state()
    changed = False
    try:
        changed |= answer_commands(state)
    except Exception as e:
        print("Command polling failed:", e)
    changed |= alert_check(state)
    if changed:
        save_state(state)
    else:                       # always persist so the rolling cache has an entry
        save_state(state)


if __name__ == "__main__":
    main()
