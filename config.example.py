# -*- coding: utf-8 -*-
# Copy this file to  config.py  and fill in your own values.
# config.py is gitignored on purpose: it holds your private token and balance.

# --- Telegram (get these from @BotFather and @userinfobot) ---
TELEGRAM_TOKEN = "PUT-YOUR-BOTFATHER-TOKEN-HERE"
ALLOWED_CHAT_IDS = [123456789]   # your numeric Telegram id(s); the bot ignores everyone else

# --- Market ---
SYMBOL = "XRPUSDT"          # analysis symbol (USDT perp = liquid price reference)
TRADE_PAIR = "XRPUSD"       # the pair you actually trade (e.g. coin-margined); shown in messages
DIRECTOR_SYMBOL = "BTCUSDT" # market "director" whose bias filters the alt

# --- Capital & risk (the balance is your margin, in the base coin) ---
BALANCE_COINS = 100.0       # initial balance in the base coin (e.g. XRP). Updatable via /saldo
RISK_PCT = 2.0              # % of balance risked per trade (the SL fixes the real risk)
RISK_PCT_HIGH = 3.0         # only for top-conviction setups (score >= SCORE_RISK_ALTO)
SCORE_RISK_ALTO = 9         # conviction score from which RISK_PCT_HIGH applies
LEV_MAX = 10               # leverage cap (keep low for coin-margined longs)
SL_MIN_PCT = 1.5           # tighter than this = noise stops you out
SL_MAX_PCT = 4.0           # wider than this = position too small

# --- Proactive alerts (the bot messages you when a setup appears) ---
PROACTIVE_ALERTS = True     # False = only reply to commands
CHECK_INTERVAL_MIN = 20     # how often (minutes) it scans the market
ALERT_MIN_SCORE = 7         # only alert setups scoring >= this (7 = solid A or better)
ALERT_HOURS_UTC = (0, 24)   # UTC hour window in which alerts may fire; (0, 24) = all day
