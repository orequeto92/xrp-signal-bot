# -*- coding: utf-8 -*-
"""Rule-based signal for a single symbol, applying a disciplined intraday method.

Pipeline: read BTC (as market director) + the symbol on 1D/4H/1H/15m, build a risk
gauge, decide LONG / SHORT / WAIT / NO-TRADE, and size the trade. It NEVER places
orders. The rules are standard technical analysis (EMA trend, market structure,
premium/discount zones, RSI anti-chase, structural stops, R-multiple targets).
"""
from . import bitget, ta
from .sizing import size_trade

TFS = ["1D", "4H", "1H", "15m"]
CLEAR = ("alcista", "bajista")


def _metrics(symbol):
    snap = bitget.snapshot(symbol, TFS, 300)
    out = {"price": snap["ticker"].get("lastPr"), "funding": snap.get("funding"),
           "oi": snap.get("oi"), "chg24": snap["ticker"].get("change24h"), "tf": {}}
    for tf in TFS:
        c = snap["candles"].get(tf) or []
        if len(c) >= 30:
            out["tf"][tf] = ta.compute(symbol, tf, c)
    return out


def _gauge(btc):
    """Simple risk gauge from BTC derivatives/volatility. Returns (color, score)."""
    score, f = 0, (btc.get("funding") or 0)
    if f > 0.0005:
        score += 2
    elif f < -0.0005:
        score += 1
    m4 = btc["tf"].get("4H", {})
    if m4.get("atr_pct") and m4["atr_pct"] > 2.5:
        score += 1
    for tf in ("1D", "4H"):
        r = (btc["tf"].get(tf) or {}).get("rsi")
        if r is not None and (r > 75 or r < 25):
            score += 1
    c = btc.get("chg24")
    if c is not None:
        if c < -0.05:
            score += 2
        elif c > 0.06:
            score += 1
    return ("ROJO" if score >= 4 else "AMARILLO" if score >= 2 else "VERDE"), score


def _director(btc):
    b4 = (btc["tf"].get("4H") or {}).get("bias")
    b1 = (btc["tf"].get("1H") or {}).get("bias")
    if b4 == "alcista" and b1 == "alcista":
        return "long"
    if b4 == "bajista" and b1 == "bajista":
        return "short"
    return ""


ATR_STOP_MULT = 2.5     # a stop must clear this many 4H ATRs, or noise takes it out


def _structural_sl(price, side, m15, m1h, m4, sl_min=1.5, sl_max=4.0):
    """Structural stop, floored by volatility. Returns (sl, ok, reason).

    A stop that sits closer than ~2x the 4H ATR gets taken out by ordinary noise
    rather than by the trade being wrong, so the structural level is widened to
    that floor. If honouring the floor would need a stop wider than sl_max, the
    setup is rejected instead of quietly using a stop that cannot hold.
    """
    atr15 = m15.get("atr") or 0
    if side == "long":
        cands = [s for s in (m1h.get("supports") or []) + (m15.get("supports") or []) if s < price]
        raw = max(cands) if cands else price * (1 - sl_min / 100)
        sl = raw - 0.3 * atr15
    else:
        cands = [r for r in (m1h.get("resistances") or []) + (m15.get("resistances") or []) if r > price]
        raw = min(cands) if cands else price * (1 + sl_min / 100)
        sl = raw + 0.3 * atr15

    # volatility floor: the stop must be at least ATR_STOP_MULT x the 4H ATR away
    atr4_pct = m4.get("atr_pct") or 0
    floor_pct = max(sl_min, atr4_pct * ATR_STOP_MULT)
    dist_pct = abs(price - sl) / price * 100

    if dist_pct < floor_pct:
        if floor_pct > sl_max:
            return None, False, ("volatilidad alta (ATR 4H %.2f%%): un stop sano exigiria "
                                 "%.2f%% (> maximo %.1f%%)." % (atr4_pct, floor_pct, sl_max))
        dist_pct = floor_pct
        sl = price * (1 - floor_pct / 100) if side == "long" else price * (1 + floor_pct / 100)
    elif dist_pct > sl_max:
        sl = price * (1 - sl_max / 100) if side == "long" else price * (1 + sl_max / 100)
    return sl, True, ""


def _space(levels, price, min_gap=0.008, n=2):
    out = []
    for lv, tag in levels:
        if all(abs(lv - x) / price > min_gap for x, _ in out):
            out.append((lv, tag))
        if len(out) >= n:
            break
    return out


def key_zones(symbol):
    """Key support/resistance/equilibrium levels to set as price alerts."""
    snap = bitget.snapshot(symbol, ("1D", "4H"), 300)
    m = {}
    for tf in ("1D", "4H"):
        c = snap["candles"].get(tf) or []
        if len(c) >= 30:
            m[tf] = ta.compute(symbol, tf, c)
    if "4H" not in m:
        return None
    price = m["4H"]["price"]
    res, sup = [], []
    for tf in ("4H", "1D"):
        if tf in m:
            for r in (m[tf].get("resistances") or []):
                if r > price * 1.004:
                    res.append((r, "resistencia %s (rompe->tendencia / rechaza->short)" % tf))
            for s in (m[tf].get("supports") or []):
                if s < price * 0.996:
                    sup.append((s, "soporte %s (en alcista=zona long / perder=debil)" % tf))
    res = _space(sorted(res), price)
    sup = _space(sorted(sup, reverse=True), price)
    levels = res + sup
    if m["4H"].get("eq"):
        levels.append((m["4H"]["eq"], "equilibrio 4H (cambia premium<->discount)"))
    levels.sort(key=lambda x: -x[0])
    return {"price": price, "levels": levels}


def evaluate(symbol, balance_coins, cfg):
    """Full evaluation. cfg is the config module (RISK_PCT, LEV_MAX, SL_MIN/MAX_PCT...)."""
    btc = _metrics(cfg.DIRECTOR_SYMBOL)
    sym = _metrics(symbol)
    price = sym["price"]
    if not price or "4H" not in sym["tf"] or "15m" not in sym["tf"]:
        return {"decision": "ERROR", "reason": "sin datos suficientes del mercado."}

    color, gscore = _gauge(btc)
    director = _director(btc)
    m4, m1h, m15 = sym["tf"].get("4H", {}), sym["tf"].get("1H", {}), sym["tf"].get("15m", {})
    bias4 = m4.get("bias")

    res = {"symbol": symbol, "price": price, "gauge": color, "director": director or "neutral",
           "oi": sym.get("oi"), "funding": sym.get("funding"),
           "rsi": {"4H": m4.get("rsi"), "1H": m1h.get("rsi"), "15m": m15.get("rsi")},
           "zona15": m15.get("zona"), "zona4": m4.get("zona")}

    # --- gates ---
    if bias4 not in CLEAR:
        res.update(decision="NO-TRADE", reason="4H sin tendencia clara (%s)." % bias4)
        return res
    side = "long" if bias4 == "alcista" else "short"
    if director and director != side:
        res.update(decision="NO-TRADE", reason="contra el sesgo director de BTC (%s)." % director)
        return res
    if color == "ROJO":
        res.update(decision="NO-TRADE", reason="Semaforo ROJO: mercado de riesgo, esperar.")
        return res

    zona = (m15.get("zona") or "")
    rsi15 = m15.get("rsi") or 50
    # zone rule + anti-chase -> if extended, WAIT for pullback (B), don't chase
    if side == "long" and ("PREMIUM" in zona or rsi15 > 68):
        res.update(decision="WAIT", side=side,
                   reason="tendencia alcista pero en premium/RSI alto: esperar pullback a discount.")
        return res
    if side == "short" and ("DISCOUNT" in zona or rsi15 < 32):
        res.update(decision="WAIT", side=side,
                   reason="tendencia bajista pero en discount/RSI bajo: esperar rebote a premium.")
        return res

    # --- build the trade ---
    entry = price
    sl, sl_ok, sl_reason = _structural_sl(price, side, m15, m1h, m4,
                                          cfg.SL_MIN_PCT, cfg.SL_MAX_PCT)
    if not sl_ok:
        res.update(decision="NO-TRADE", side=side, reason=sl_reason)
        return res
    contract = None
    try:
        contract = bitget.contract(symbol)
    except Exception:
        pass
    # --- conviction score (base 5) ---
    score = 5
    if director == side:
        score += 1
    if color == "VERDE":
        score += 1
    if (side == "long" and "DISCOUNT" in zona) or (side == "short" and "PREMIUM" in zona):
        score += 1
    if (m1h.get("bias") == bias4):
        score += 1
    if side == "long":
        score -= 1                                   # coin-margined long = double risk
    divs = " ".join(m15.get("divergences") or [])
    if (side == "long" and "bajista" in divs) or (side == "short" and "alcista" in divs):
        score -= 1
    if color == "AMARILLO":
        score -= 1
    score = max(1, min(10, score))
    grade = "A+" if score >= 8 else "A" if score >= 6 else "B"

    # Conviction-based risk: only the very best setups (9-10) get the larger size.
    # Everything else stays at the base risk. Never scale beyond RISK_PCT_HIGH.
    risk_pct = cfg.RISK_PCT
    if score >= getattr(cfg, "SCORE_RISK_ALTO", 9):
        risk_pct = getattr(cfg, "RISK_PCT_HIGH", cfg.RISK_PCT)

    bal_usd = balance_coins * price
    sz = size_trade(entry, sl, side, bal_usd, risk_pct, cfg.LEV_MAX,
                    contract, cfg.SL_MIN_PCT, cfg.SL_MAX_PCT)
    sz["risk_pct"] = risk_pct

    res.update(decision="TRADE", side=side, entry=entry, sl=round(sl, 6),
               tp1=sz.get("tp1"), tp2=sz.get("tp2"), score=score, grade=grade,
               sizing=sz, reason="setup %s %s (score %d/10)." % (grade, side, score))
    if score <= 5:                                   # below threshold -> only watch
        res["decision"] = "WATCH"
        res["reason"] = "setup %s pero score %d/10 (<=5): vigilar, no entrar." % (grade, score)
    elif not director and score < 8:                 # BTC neutral -> solo A+ (score>=8)
        res["decision"] = "WATCH"
        res["reason"] = ("BTC sin sesgo director: solo se opera A+ (score>=8). "
                         "Este es %s (score %d/10): vigilar." % (grade, score))
    return res
