#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
XRP Signal Bot — a local, read-only Telegram bot that applies a disciplined
intraday rule-set to a coin-margined perp and reports opportunities, plus simple
compound-balance tracking. It NEVER places orders: it only reads public market
data and proposes; you execute manually on your exchange.

Run:  python bot.py     (needs config.py — copy config.example.py and fill it in)
Stdlib only. Long-polling against the Telegram Bot API.

Replies are instant while this process runs. For answers with the PC off, the
GitHub Actions workflow polls commands on a schedule (see .github/workflows/).
"""
import sys, os, json, time, urllib.request, urllib.parse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
try:
    import config
except Exception:
    sys.exit("Missing config.py — copy config.example.py to config.py and fill it in.")

from engine import signal, commands
from engine.format import describe as _describe

API = "https://api.telegram.org/bot%s/" % config.TELEGRAM_TOKEN
STATE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "state.json")


# ---------- state (balance + trade log) ----------
def load_state():
    try:
        return json.load(open(STATE, encoding="utf-8"))
    except Exception:
        return {"balance_coins": float(getattr(config, "BALANCE_COINS", 0)),
                "initial_coins": float(getattr(config, "BALANCE_COINS", 0)), "trades": []}


def save_state(s):
    os.makedirs(os.path.dirname(STATE), exist_ok=True)
    json.dump(s, open(STATE, "w", encoding="utf-8"), indent=1, ensure_ascii=False)


# ---------- telegram api ----------
def api_call(method, params):
    data = urllib.parse.urlencode(params).encode()
    req = urllib.request.Request(API + method, data=data, headers={"User-Agent": "xrp-signal-bot"})
    try:
        return json.load(urllib.request.urlopen(req, timeout=70))
    except Exception:
        return None


def send(chat_id, text):
    api_call("sendMessage", {"chat_id": chat_id, "text": text})


# ---------- proactive alerts ----------
def proactive_check(state):
    """Scan the market; push ONE alert when a fresh high-conviction setup appears."""
    if not getattr(config, "PROACTIVE_ALERTS", False):
        return
    lo, hi = getattr(config, "ALERT_HOURS_UTC", (0, 24))
    h = time.gmtime().tm_hour
    in_window = (lo <= h < hi) if lo <= hi else (h >= lo or h < hi)
    if not in_window:
        return
    try:
        d = signal.evaluate(config.SYMBOL, state["balance_coins"], config)
    except Exception:
        return
    min_score = getattr(config, "ALERT_MIN_SCORE", 7)
    actionable = d.get("decision") == "TRADE" and d.get("score", 0) >= min_score
    sig = ("%s-%s-%d" % (d.get("side"), d.get("grade"), d.get("score"))) if actionable else None
    # anti-spam: only send when the actionable signature is new
    if sig and sig != state.get("last_alert_sig"):
        msg = "🔔 OPORTUNIDAD en %s\n\n%s" % (
            config.TRADE_PAIR, _describe(d, config.SYMBOL, config.TRADE_PAIR, config.RISK_PCT))
        for chat in config.ALLOWED_CHAT_IDS:
            send(chat, msg)
    if state.get("last_alert_sig") != sig:
        state["last_alert_sig"] = sig
        save_state(state)


def main():
    if "PUT-YOUR" in config.TELEGRAM_TOKEN or not config.ALLOWED_CHAT_IDS:
        sys.exit("Configure TELEGRAM_TOKEN and ALLOWED_CHAT_IDS in config.py first.")
    print("XRP Signal Bot running. Whitelisted chats:", config.ALLOWED_CHAT_IDS)
    interval = getattr(config, "CHECK_INTERVAL_MIN", 20) * 60
    last_check = 0
    offset = None
    while True:
        # proactive scan on its own timer (runs even if no messages arrive)
        if getattr(config, "PROACTIVE_ALERTS", False) and time.time() - last_check >= interval:
            last_check = time.time()
            try:
                proactive_check(load_state())
            except Exception:
                pass
        params = {"timeout": 60}
        if offset is not None:
            params["offset"] = offset
        upd = api_call("getUpdates", params)
        if not upd or not upd.get("ok"):
            time.sleep(3)
            continue
        for u in upd["result"]:
            offset = u["update_id"] + 1
            msg = u.get("message") or u.get("edited_message")
            if not msg or "text" not in msg:
                continue
            chat_id = msg["chat"]["id"]
            if chat_id not in config.ALLOWED_CHAT_IDS:
                continue                       # ignore everyone but the owner
            state = load_state()
            try:
                reply, changed = commands.handle(msg["text"], state, config)
                if changed:
                    save_state(state)
            except Exception as e:
                reply = "Error procesando el comando: %s" % e
            send(chat_id, reply)


if __name__ == "__main__":
    main()
