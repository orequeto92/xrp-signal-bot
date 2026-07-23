#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
XRP Signal Bot — a local, read-only Telegram bot that applies a disciplined
intraday rule-set to a coin-margined perp and reports opportunities, plus simple
compound-balance tracking. It NEVER places orders: it only reads public market
data and proposes; you execute manually on your exchange.

Run:  python bot.py     (needs config.py — copy config.example.py and fill it in)
Stdlib only. Long-polling against the Telegram Bot API.
"""
import sys, os, json, time, urllib.request, urllib.parse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
try:
    import config
except Exception:
    sys.exit("Missing config.py — copy config.example.py to config.py and fill it in.")

from engine import signal, bitget

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


# ---------- formatting ----------
def price_of():
    try:
        return bitget.futures_info(config.SYMBOL).get("lastPrice")
    except Exception:
        return None


def fmt_balance(s):
    px = price_of()
    bal = s["balance_coins"]
    usd = (bal * px) if px else None
    line = "Saldo: %.4f %s" % (bal, config.SYMBOL.replace("USDT", ""))
    if usd:
        line += "  (~$%.2f)" % usd
    return line


def cmd_help():
    return ("XRP Signal Bot — comandos:\n"
            "/oportunidades  setup segun las reglas (o no-trade)\n"
            "/saldo          ver saldo actual\n"
            "/saldo 13.75    fijar saldo (interes compuesto)\n"
            "/registrar +0.34  sumar P&L de un trade (en la moneda) y guardarlo\n"
            "/estado         estadisticas y crecimiento\n"
            "/alertas        zonas clave para alertas de precio\n\n"
            "AVISO: el bot NO opera. Propone; tu ejecutas en el exchange. "
            "Material educativo, no asesoria financiera.")


def describe(d):
    """Format an evaluation result as a Telegram message."""
    base = config.SYMBOL.replace("USDT", "")
    L = ["=== %s === precio $%.4f" % (config.TRADE_PAIR, d["price"]),
         "Semaforo: %s | Director BTC: %s" % (d["gauge"], d["director"]),
         "RSI 4H/1H/15m: %s | Zona 15m: %s" % (
             "/".join("%.0f" % v if v else "-" for v in
                      (d["rsi"]["4H"], d["rsi"]["1H"], d["rsi"]["15m"])), d.get("zona15") or "-")]
    dec = d["decision"]
    if dec == "NO-TRADE":
        L.append("\n>> NO-TRADE: %s" % d["reason"])
    elif dec == "WAIT":
        L.append("\n>> ESPERAR (%s): %s" % (d.get("side", "").upper(), d["reason"]))
    elif dec == "WATCH":
        L.append("\n>> VIGILAR: %s" % d["reason"])
    elif dec == "TRADE":
        sz = d["sizing"]
        L.append("\n>> SETUP %s  %s  (score %d/10)" % (d["grade"], d["side"].upper(), d["score"]))
        L.append("Entrada ~$%.4f | SL $%.4f | TP1 $%.4f | TP2 $%.4f" %
                 (d["entry"], d["sl"], d["tp1"], d["tp2"]))
        L.append("Cantidad %.4g %s | notional $%.2f | margen $%.2f | %dx" %
                 (sz["qty"], base, sz["notional"], sz["margin"], sz["leverage"]))
        L.append("Riesgo $%.2f (%.1f%%) | liquidacion ~%.1f%% vs SL %.2f%%" %
                 (sz["risk_usd"], config.RISK_PCT, sz["liq_pct"], sz["dist_pct"]))
        for w in sz.get("warnings", []):
            L.append("! " + w)
        if d["side"] == "long":
            L.append("Recuerda: long coin-margined = riesgo doble. Considera menos lev.")
        L.append("Tras TP1: cierra 50% y mueve SL a break-even. Tu ejecutas en el exchange.")
    return "\n".join(L)


def cmd_oportunidades(s):
    d = signal.evaluate(config.SYMBOL, s["balance_coins"], config)
    if d.get("decision") == "ERROR":
        return "No pude analizar: %s" % d.get("reason")
    return describe(d)


def cmd_saldo(s, arg):
    if arg:
        try:
            s["balance_coins"] = float(arg.replace(",", "."))
            save_state(s)
            return "Saldo actualizado.\n" + fmt_balance(s)
        except ValueError:
            return "Uso: /saldo 13.75"
    return fmt_balance(s)


def cmd_registrar(s, arg):
    try:
        pnl = float(arg.replace("+", "").replace(",", "."))
    except (ValueError, AttributeError):
        return "Uso: /registrar +0.34   (P&L en la moneda; usa - para perdidas)"
    s["balance_coins"] = round(s["balance_coins"] + pnl, 8)
    s.setdefault("trades", []).append(
        {"ts": int(time.time()), "pnl_coins": pnl, "balance_after": s["balance_coins"]})
    save_state(s)
    return "Registrado P&L %+.4f.\n%s\nTrades: %d" % (pnl, fmt_balance(s), len(s["trades"]))


def cmd_estado(s):
    tr = s.get("trades", [])
    wins = sum(1 for t in tr if t["pnl_coins"] > 0)
    losses = sum(1 for t in tr if t["pnl_coins"] < 0)
    pnl = sum(t["pnl_coins"] for t in tr)
    init = s.get("initial_coins") or s["balance_coins"]
    growth = (s["balance_coins"] / init - 1) * 100 if init else 0
    wr = (wins / (wins + losses) * 100) if (wins + losses) else 0
    return ("%s\nInicial: %.4f | crecimiento: %+.1f%%\n"
            "Trades: %d (W %d / L %d) | acierto %.0f%%\nP&L acumulado: %+.4f" %
            (fmt_balance(s), init, growth, len(tr), wins, losses, wr, pnl))


def cmd_alertas():
    z = signal.key_zones(config.SYMBOL)
    if not z:
        return "No pude leer zonas."
    L = ["Zonas para alertas en %s (precio $%.4f):" % (config.TRADE_PAIR, z["price"])]
    for lv, tag in z["levels"]:
        L.append("  %.4f  %s" % (lv, tag))
    L.append("La alerta es aviso para MIRAR: cuando salte, pide /oportunidades.")
    return "\n".join(L)


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
        msg = "🔔 OPORTUNIDAD en %s\n\n%s" % (config.TRADE_PAIR, describe(d))
        for chat in config.ALLOWED_CHAT_IDS:
            send(chat, msg)
    if state.get("last_alert_sig") != sig:
        state["last_alert_sig"] = sig
        save_state(state)


# ---------- dispatch ----------
def handle(chat_id, text, state):
    parts = text.strip().split(maxsplit=1)
    cmd = parts[0].lower().lstrip("/").split("@")[0]
    arg = parts[1].strip() if len(parts) > 1 else ""
    if cmd in ("start", "help"):
        return cmd_help()
    if cmd in ("oportunidades", "op"):
        return cmd_oportunidades(state)
    if cmd == "saldo":
        return cmd_saldo(state, arg)
    if cmd == "registrar":
        return cmd_registrar(state, arg)
    if cmd == "estado":
        return cmd_estado(state)
    if cmd == "alertas":
        return cmd_alertas()
    return "Comando no reconocido. /help para ver los comandos."


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
                reply = handle(chat_id, msg["text"], state)
            except Exception as e:
                reply = "Error procesando el comando: %s" % e
            send(chat_id, reply)


if __name__ == "__main__":
    main()
