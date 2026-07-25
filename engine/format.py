# -*- coding: utf-8 -*-
"""Shared message formatting, usable both by the local bot (bot.py) and the
GitHub Actions script (scripts/gh_action_check.py). No config.py dependency —
everything needed is passed in explicitly."""


def describe(d, symbol, trade_pair, risk_pct):
    """Format a signal.evaluate() result as a plain-text message."""
    base = symbol.replace("USDT", "")
    L = ["=== %s === precio $%.4f" % (trade_pair, d["price"]),
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
                 (sz["risk_usd"], risk_pct, sz["liq_pct"], sz["dist_pct"]))
        for w in sz.get("warnings", []):
            L.append("! " + w)
        if d["side"] == "long":
            L.append("Recuerda: long coin-margined = riesgo doble. Considera menos lev.")
        L.append("Tras TP1: cierra 50% y mueve SL a break-even. Tu ejecutas en el exchange.")
    return "\n".join(L)
