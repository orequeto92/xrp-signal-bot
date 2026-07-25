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

Two ways to get alerts without keeping your PC on:

- **GitHub Actions (recommended, no server, no card needed)** — a scheduled workflow
  checks the market every ~20 min and pushes a Telegram message only when a fresh
  high-conviction setup appears. Interactive commands (`/oportunidades`, `/saldo`...)
  still require running `bot.py` locally when you want them. See
  **[.github/workflows/alerts.yml](.github/workflows/alerts.yml)** and the setup below.
- **A small always-on VM** — runs the *full* interactive bot (commands + alerts) around
  the clock. See **[deploy/DEPLOY.md](deploy/DEPLOY.md)** for a free Oracle Cloud VM
  guide (needs a cloud account); the same `systemd` service file works on any Linux VPS.

#### Setting up the GitHub Actions alerts

1. Fork or push this repo to your own GitHub account.
2. In your repo: **Settings → Secrets and variables → Actions → New repository secret**.
   Add three secrets:
   - `TELEGRAM_TOKEN` — your bot token from BotFather
   - `TELEGRAM_CHAT_ID` — your numeric Telegram id (from @userinfobot)
   - `BALANCE_COINS` — your margin balance (e.g. `13.37`), used for position sizing in alerts
3. That's it — the workflow runs automatically on its schedule (every ~20 min, only
   during the configured daytime hours). To test it right away instead of waiting:
   **Actions tab → "XRP Opportunity Alerts" → Run workflow**.
4. Check the run's log to confirm it worked ("Alert sent: ..." or "No new alert...").

Notes:
- Public repos get **unlimited free Actions minutes** — this costs nothing to run.
- GitHub **disables scheduled workflows after 60 days of repo inactivity** — push any
  commit (or just re-enable it from the Actions tab) to keep it alive if that happens.
- The schedule is UTC-based; edit the `cron:` line in the workflow file to change hours.

## Data source

Public market data from the Bitget API (no API key, read-only). No trading credentials
are ever used or stored.

## Disclaimer

This software is provided for educational purposes only and is **not financial advice**.
Trading leveraged crypto derivatives can lose your entire capital. Coin-margined longs
carry extra risk (your collateral falls in value as the position loses). You are solely
responsible for your decisions. See [LICENSE](LICENSE) (MIT).
