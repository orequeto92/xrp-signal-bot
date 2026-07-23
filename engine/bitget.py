# -*- coding: utf-8 -*-
"""
Capa de datos para el exchange Bitget (API publica v2, sin API key).

Misma interfaz que el antiguo lbank.py, para que analizar.py solo cambie el import:
- candles(symbol, tf, limit)  -> [ts_seg, o, h, l, c, vol] (mas antigua primero)
- futures_info(symbol)        -> precio, cambio 24h, funding y OI (Bitget SI expone OI)
- snapshot(symbol, tfs, limit)-> dict con ticker/funding/oi/candles

Ventajas sobre LBank: velas SEMANALES (1W) nativas y Open Interest por moneda.
NO ejecuta ordenes.
"""
import json, time, urllib.request, urllib.parse

BASE = "https://api.bitget.com"
PT = "USDT-FUTURES"

# nuestro TF -> granularidad Bitget FUTUROS (H/D/W mayuscula) y segundos por vela
TF = {
    "15m": ("15m", 900),
    "1H":  ("1H", 3600),
    "4H":  ("4H", 14400),
    "1D":  ("1D", 86400),
    "1W":  ("1W", 604800),
}
# nuestro TF -> granularidad Bitget SPOT (los codigos difieren del de futuros).
# El spot tiene ANOS de historia semanal; el futuro perp de XRP/XLM es reciente
# (~13 semanas), asi que el carril de acumulacion lee del SPOT.
TF_SPOT = {
    "15m": "15min", "1H": "1h", "4H": "4h", "1D": "1day", "1W": "1week",
}

_TICK_CACHE = {"ts": 0, "data": {}}


def _get(path, params, timeout=20):
    url = BASE + path + "?" + urllib.parse.urlencode(params)
    for attempt in range(3):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return json.load(r)
        except Exception:
            if attempt == 2:
                return None
            time.sleep(1.0)
    return None


def candles(symbol, tf, limit=300, market="futures"):
    """Velas Bitget -> [ts_seg, open, high, low, close, vol] (mas antigua primero).
    market='futures' (perp USDT) o 'spot' (para el carril de acumulacion, con anos de historia)."""
    if market == "spot":
        if tf not in TF_SPOT:
            return []
        d = _get("/api/v2/spot/market/candles",
                 {"symbol": symbol.upper(), "granularity": TF_SPOT[tf],
                  "limit": str(min(limit, 1000))})
    else:
        if tf not in TF:
            return []
        d = _get("/api/v2/mix/market/candles",
                 {"symbol": symbol.upper(), "productType": PT,
                  "granularity": TF[tf][0], "limit": str(min(limit, 1000))})
    if not d or not d.get("data"):
        return []
    out = []
    for row in d["data"]:                 # [ts_ms, o, h, l, c, baseVol, quoteVol, ...]
        if len(row) >= 6:
            out.append([int(int(row[0]) / 1000)] + [float(x) for x in row[1:6]])
    return out


def _ticker(symbol):
    """Ticker de futuros (cache 30s por todos los simbolos consultados)."""
    sym = symbol.upper()
    if time.time() - _TICK_CACHE["ts"] < 30 and sym in _TICK_CACHE["data"]:
        return _TICK_CACHE["data"][sym]
    d = _get("/api/v2/mix/market/ticker", {"symbol": sym, "productType": PT})
    row = (d.get("data") or [{}])[0] if d else {}
    if row:
        _TICK_CACHE["data"][sym] = row
        _TICK_CACHE["ts"] = time.time()
    return row


def futures_info(symbol):
    """Precio, cambio 24h, funding, OI (base y USD) e index price para 'XRPUSDT'."""
    r = _ticker(symbol)
    if not r:
        return {}
    def f(k):
        try:
            return float(r.get(k))
        except Exception:
            return None
    last = f("lastPr")
    oi_base = f("holdingAmount")                     # OI en unidades base (contratos)
    oi_usd = oi_base * last if (oi_base and last) else None
    return {"lastPrice": last, "change24h": f("change24h"), "fundingRate": f("fundingRate"),
            "oi_base": oi_base, "oi_usd": oi_usd, "index": f("indexPrice"),
            "high": r.get("high24h"), "low": r.get("low24h"), "volume": r.get("baseVolume")}


_CONTRACTS = {"ts": 0, "data": {}}


def contract(symbol):
    """Specs del contrato perp: min de orden, step de tamano e index price.
    Devuelve {'symbol','min','tick','px'} o None (misma forma que usaba reto.py)."""
    sym = symbol.upper().replace("USDT", "") + "USDT"
    if time.time() - _CONTRACTS["ts"] > 300 or not _CONTRACTS["data"]:
        d = _get("/api/v2/mix/market/contracts", {"productType": PT})
        idx = {}
        if d and d.get("data"):
            for r in d["data"]:
                idx[r.get("symbol")] = r
        _CONTRACTS["data"] = idx
        _CONTRACTS["ts"] = time.time()
    r = _CONTRACTS["data"].get(sym)
    if not r:
        return None
    try:
        minv = float(r.get("minTradeNum"))
        tick = float(r.get("sizeMultiplier") or minv)   # step de tamano de orden
    except Exception:
        return None
    px = futures_info(sym).get("index") or futures_info(sym).get("lastPrice")
    return {"symbol": sym, "min": minv, "tick": tick, "px": px}


def snapshot(symbol, tfs=("1D", "4H", "1H", "15m"), limit=300, market="futures"):
    # Precio/funding/OI siempre del ticker de futuros (sentimiento de derivados).
    # Las VELAS salen del mercado pedido: 'futures' (intradia) o 'spot' (acumulacion).
    fi = futures_info(symbol)
    out = {"symbol": symbol,
           "ticker": {"lastPr": fi.get("lastPrice"), "change24h": fi.get("change24h")},
           "funding": fi.get("fundingRate"),
           "oi": fi.get("oi_usd"),          # Bitget SI expone OI (en USD)
           "oi_base": fi.get("oi_base"),
           "market": market,
           "candles": {}}
    for tf in tfs:
        out["candles"][tf] = candles(symbol, tf, limit, market=market)
    return out
