# XRP Signal Bot

A small, **local** Telegram bot that applies a disciplined intraday rule-set to a
perpetual futures pair (XRP by default) and reports trade opportunities on demand —
so you can check the market from your phone while away from your desk. It also keeps
a simple **compound-balance** log.

> **It never places orders.** The bot only reads public market data and *proposes*;
> you execute manually on your exchange. Educational tool, **not financial advice.**

## What it does

- **`/oportunidades`** — runs the engine and returns a setup (direction, entry, stop,
  targets, size, conviction score 1–10) or a clear *no-trade / wait* verdict.
- **`/saldo`** / **`/saldo 13.75`** — view or set your margin balance.
- **`/registrar +0.34`** — add a trade's P&L to the balance (compound tracking) and log it.
- **`/estado`** — balance, growth, trade count, win rate.
- **`/alertas`** — key support/resistance/equilibrium levels to set as exchange price alerts.

Only the whitelisted Telegram user(s) in `config.py` get answers; everyone else is ignored.

## The method (standard technical analysis)

The signal is **rule-based and transparent** — no black box, no "predictions":

1. **Market director** — checks the majors (BTC) trend as a bias filter for the alt.
2. **Risk gauge** — a simple green/amber/red read from funding, volatility and RSI extremes.
3. **Trend** — only trades when the 4H has a clear trend (price/EMA structure); skips chop.
4. **Zone** — longs only in *discount/equilibrium*, shorts only in *premium/equilibrium*
   (buy low / sell high within the trend); never chases extended RSI.
5. **Risk** — structural stop-loss, position sized to risk a fixed % of the balance,
   R-multiple targets, leverage capped.
6. **Conviction score (1–10)** — confluences add, cautions subtract; low scores downgrade
   to *watch* instead of a trade.

## Setup

Requires **Python 3.8+** (standard library only — no `pip install` needed).

1. Create a bot with **[@BotFather](https://t.me/BotFather)** → copy the token.
2. Get your numeric Telegram id from **[@userinfobot](https://t.me/userinfobot)**.
3. Copy the config template and fill it in:
   ```
   cp config.example.py config.py
   ```
   Set `TELEGRAM_TOKEN`, `ALLOWED_CHAT_IDS`, and your `BALANCE_COINS`.
4. Run it:
   ```
   python bot.py
   ```
   Keep the process running (your PC must stay on to answer). Message your bot `/help`.

`config.py` and `data/state.json` are gitignored — your token and balance stay private.

### Run it 24/7 (without keeping your PC on)

To have it answer around the clock, deploy it on a small always-on host. See
**[deploy/DEPLOY.md](deploy/DEPLOY.md)** for a step-by-step guide to a **free** Oracle
Cloud Always Free VM running the bot as an auto-restarting `systemd` service. The same
service file works on any Linux VPS.

## Data source

Public market data from the Bitget API (no API key, read-only). No trading credentials
are ever used or stored.

## Disclaimer

This software is provided for educational purposes only and is **not financial advice**.
Trading leveraged crypto derivatives can lose your entire capital. Coin-margined longs
carry extra risk (your collateral falls in value as the position loses). You are solely
responsible for your decisions. See [LICENSE](LICENSE) (MIT).
