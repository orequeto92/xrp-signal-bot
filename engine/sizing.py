# -*- coding: utf-8 -*-
"""Position sizing for a coin-margined perp, risking a fixed % of the account.

The account balance is expressed as an amount of the base coin (e.g. XRP) held as
margin; we value it in USD (coins * price) and risk `risk_pct` of that per trade.
The stop-loss distance defines the real risk, not the leverage. This is a linear
approximation: a real inverse (coin-margined) contract liquidates slightly earlier
on longs, so keep leverage modest.
"""


def size_trade(entry, sl, side, balance_usd, risk_pct=2.0, lev_max=10,
               contract=None, sl_min_pct=1.5, sl_max_pct=4.0):
    """Return a dict with quantity, notional, margin, leverage, TP1/TP2 and warnings."""
    dist = abs(entry - sl)
    if dist <= 0 or entry <= 0:
        return {"error": "entry and SL must differ and be positive"}
    dist_pct = dist / entry * 100.0
    risk_usd = balance_usd * risk_pct / 100.0

    notional_ideal = risk_usd / (dist_pct / 100.0)
    lev_safe = max(1, int((100.0 / dist_pct) / 3.0))     # liquidation >= 3x the SL
    lev = max(1, min(lev_max, lev_safe))

    warnings = []
    if dist_pct < sl_min_pct:
        warnings.append("SL tight (%.2f%% < %.1f%%): noise may stop you out." % (dist_pct, sl_min_pct))
    elif dist_pct > sl_max_pct:
        warnings.append("SL wide (%.2f%%): position becomes tiny." % dist_pct)

    # round to the contract's min/step if we have it
    if contract:
        qty_ideal = notional_ideal / entry
        step = contract.get("tick") or contract.get("min") or 1
        steps = max(1, round(qty_ideal / step))
        qty = steps * step
        if qty < contract.get("min", qty):
            qty = contract["min"]
    else:
        qty = notional_ideal / entry
    notional = qty * entry
    margin = notional / lev

    if side.lower() == "long":
        tp1, tp2 = entry + dist, entry + dist * 2
    else:
        tp1, tp2 = entry - dist, entry - dist * 2

    liq_pct = 100.0 / lev
    return {
        "dist_pct": round(dist_pct, 2),
        "risk_usd": round(risk_usd, 2),
        "qty": round(qty, 6),
        "notional": round(notional, 2),
        "margin": round(margin, 2),
        "leverage": lev,
        "liq_pct": round(liq_pct, 1),
        "liq_ok": liq_pct > dist_pct * 3,
        "tp1": round(tp1, 6),
        "tp2": round(tp2, 6),
        "warnings": warnings,
    }
