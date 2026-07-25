# -*- coding: utf-8 -*-
"""Command handling shared by the local bot (bot.py) and the GitHub Actions
runner (scripts/gh_action_check.py).

Handlers never persist state themselves: `handle()` returns (reply, changed) and
the caller decides how/where to save. `cfg` only needs the attributes that
engine.signal and engine.format read (SYMBOL, TRADE_PAIR, RISK_PCT, ...).
"""
import time

from . import signal
from .format import describe


HELP = ("XRP Signal Bot — comandos:\n"
        "/oportunidades  setup segun las reglas (o no-trade)\n"
        "/saldo          ver saldo actual\n"
        "/saldo 13.75    fijar saldo (interes compuesto)\n"
        "/registrar +0.34  sumar P&L de un trade (en la moneda) y guardarlo\n"
        "/estado         estadisticas y crecimiento\n"
        "/alertas        zonas clave para alertas de precio\n\n"
        "AVISO: el bot NO opera. Propone; tu ejecutas en el exchange. "
        "Material educativo, no asesoria financiera.")


def _price(cfg):
    from . import bitget
    try:
        return bitget.futures_info(cfg.SYMBOL).get("lastPrice")
    except Exception:
        return None


def fmt_balance(state, cfg):
    px = _price(cfg)
    bal = state["balance_coins"]
    line = "Saldo: %.4f %s" % (bal, cfg.SYMBOL.replace("USDT", ""))
    if px:
        line += "  (~$%.2f)" % (bal * px)
    return line


def cmd_oportunidades(state, cfg):
    d = signal.evaluate(cfg.SYMBOL, state["balance_coins"], cfg)
    if d.get("decision") == "ERROR":
        return "No pude analizar: %s" % d.get("reason")
    return describe(d, cfg.SYMBOL, cfg.TRADE_PAIR, cfg.RISK_PCT)


def cmd_saldo(state, cfg, arg):
    if arg:
        try:
            state["balance_coins"] = float(arg.replace(",", "."))
        except ValueError:
            return "Uso: /saldo 13.75", False
        return "Saldo actualizado.\n" + fmt_balance(state, cfg), True
    return fmt_balance(state, cfg), False


def cmd_registrar(state, cfg, arg):
    try:
        pnl = float(arg.replace("+", "").replace(",", "."))
    except (ValueError, AttributeError):
        return "Uso: /registrar +0.34   (P&L en la moneda; usa - para perdidas)", False
    state["balance_coins"] = round(state["balance_coins"] + pnl, 8)
    state.setdefault("trades", []).append(
        {"ts": int(time.time()), "pnl_coins": pnl, "balance_after": state["balance_coins"]})
    return ("Registrado P&L %+.4f.\n%s\nTrades: %d"
            % (pnl, fmt_balance(state, cfg), len(state["trades"])), True)


def cmd_estado(state, cfg):
    tr = state.get("trades", [])
    wins = sum(1 for t in tr if t["pnl_coins"] > 0)
    losses = sum(1 for t in tr if t["pnl_coins"] < 0)
    pnl = sum(t["pnl_coins"] for t in tr)
    init = state.get("initial_coins") or state["balance_coins"]
    growth = (state["balance_coins"] / init - 1) * 100 if init else 0
    wr = (wins / (wins + losses) * 100) if (wins + losses) else 0
    return ("%s\nInicial: %.4f | crecimiento: %+.1f%%\n"
            "Trades: %d (W %d / L %d) | acierto %.0f%%\nP&L acumulado: %+.4f"
            % (fmt_balance(state, cfg), init, growth, len(tr), wins, losses, wr, pnl))


def cmd_alertas(cfg):
    z = signal.key_zones(cfg.SYMBOL)
    if not z:
        return "No pude leer zonas."
    L = ["Zonas para alertas en %s (precio $%.4f):" % (cfg.TRADE_PAIR, z["price"])]
    for lv, tag in z["levels"]:
        L.append("  %.4f  %s" % (lv, tag))
    L.append("La alerta es aviso para MIRAR: cuando salte, pide /oportunidades.")
    return "\n".join(L)


def handle(text, state, cfg):
    """Dispatch a command. Returns (reply_text, state_changed)."""
    parts = (text or "").strip().split(maxsplit=1)
    if not parts:
        return "Comando no reconocido. /help para ver los comandos.", False
    cmd = parts[0].lower().lstrip("/").split("@")[0]
    arg = parts[1].strip() if len(parts) > 1 else ""

    if cmd in ("start", "help"):
        return HELP, False
    if cmd in ("oportunidades", "op"):
        return cmd_oportunidades(state, cfg), False
    if cmd == "saldo":
        return cmd_saldo(state, cfg, arg)
    if cmd == "registrar":
        return cmd_registrar(state, cfg, arg)
    if cmd == "estado":
        return cmd_estado(state, cfg), False
    if cmd == "alertas":
        return cmd_alertas(cfg), False
    return "Comando no reconocido. /help para ver los comandos.", False
