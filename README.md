# Crypto Futures Signal Analysis Bot

A modular Python project that analyses cryptocurrency markets and outputs trading signals.

> **No trades are executed. No Binance API is required.**

📊 **Live Dashboard (GitHub Pages):** signals are automatically published every 30 minutes via GitHub Actions.
> Enable GitHub Pages in your repo settings (Settings → Pages → Source: **GitHub Actions**) to activate the dashboard.

---

## Features

- Fetches OHLCV data from public APIs (CryptoCompare, CoinGecko)
- Technical indicators: RSI, SMA, EMA, MACD, Bollinger Bands, Stochastic, ATR, VWAP, Ichimoku, Fibonacci
- Volume analysis: spike detection, trend, divergence
- Market structure: trend classification, Break of Structure (BOS), Change of Character (CHOCH)
- Candlestick pattern recognition: Doji, Hammer, Shooting Star, Pin Bar, Engulfing patterns
- Support & resistance zones from swing highs/lows
- Scoring-based signal engine: LONG / SHORT / NO TRADE
- Risk management: ATR-based stop loss & take profit (default 1:3 RR)
- **GitHub Pages dashboard** – live signal cards, auto-refreshes every 5 minutes

---

## Project Structure

```
crypto_signal_bot/
├── config/
│   └── settings.py          # Configuration (env vars + defaults)
├── data/
│   └── data_fetcher.py      # OHLCV data from public APIs
├── analysis/
│   ├── indicators.py         # Technical indicators
│   ├── volume_analysis.py    # Volume analysis
│   ├── market_structure.py   # Trend & structure detection
│   ├── candlestick_patterns.py # Candlestick pattern recognition
│   └── support_resistance.py # Support/resistance levels
├── strategy/
│   ├── signal_engine.py      # Signal scoring & generation
│   └── risk_management.py    # Entry, SL, TP, RR calculation
├── utils/
│   └── logger.py             # Logging utility
└── main.py                   # Entry point
```

---

## Requirements

- Python 3.11+
- See `requirements.txt`

---

## Installation

```bash
# 1. Clone the repository
git clone https://github.com/abidkhancu/bot.git
cd bot

# 2. Create a virtual environment
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt
```

---

## Configuration

Copy the example environment file and edit as needed:

```bash
cp .env.example .env
```

### Available environment variables

| Variable               | Default                        | Description                              |
|------------------------|--------------------------------|------------------------------------------|
| `PAIRS`                | `BTC/USDT,ETH/USDT,SOL/USDT`  | Comma-separated pairs to analyse         |
| `TIMEFRAMES`           | `15m,1h,4h`                    | Comma-separated timeframes               |
| `DATA_SOURCE`          | `cryptocompare`                | `cryptocompare` or `coingecko`           |
| `CRYPTOCOMPARE_API_KEY`| _(empty)_                      | Optional – increases rate limits         |
| `CANDLE_LIMIT`         | `200`                          | Number of candles per request            |
| `LONG_THRESHOLD`       | `6`                            | Minimum score to generate a LONG signal  |
| `SHORT_THRESHOLD`      | `-6`                           | Maximum score to generate a SHORT signal |
| `RISK_REWARD_RATIO`    | `3.0`                          | Take profit = SL distance × ratio        |
| `RUN_INTERVAL_MINUTES` | `15`                           | Minutes between runs in loop mode        |
| `LOG_LEVEL`            | `INFO`                         | Logging level                            |
| `LOG_FILE`             | `crypto_signal_bot.log`        | Path to rotating log file                |

---

## Usage

### Run once

```bash
python -m crypto_signal_bot.main
```

### Run continuously (every `RUN_INTERVAL_MINUTES` minutes)

```bash
python -m crypto_signal_bot.main --loop
```

### Export signals as JSON (for the GitHub Pages dashboard)

```bash
python -m crypto_signal_bot.main --export-json docs/signals.json
```

---

## GitHub Pages Dashboard

The repository includes a `.github/workflows/pages.yml` workflow that:

1. Installs Python dependencies
2. Runs the bot and saves signals to `docs/signals.json`
3. Deploys the `docs/` folder to GitHub Pages

### Enable it in your fork

1. Go to **Settings → Pages**
2. Set **Source** to **GitHub Actions**
3. Push to the default branch or trigger the workflow manually from the **Actions** tab

The dashboard will be available at:
```
https://<your-username>.github.io/<your-repo>/
```

It auto-refreshes every 5 minutes in the browser and is redeployed by CI every 30 minutes.

### Dashboard features

- Signal cards for each pair/timeframe combination
- Color-coded badges: 🟢 LONG · 🔴 SHORT · ⚪ No Trade
- Entry, Stop Loss, Take Profit prices
- RSI, trend, candlestick pattern, volume info
- Confidence bar and score breakdown
- Support / resistance levels
- Filter chips (All / Long / Short / No Trade)
- Dark theme optimised for trading dashboards



```
============================================================
  PAIR:       BTC/USDT
  TIMEFRAME:  15m

  SIGNAL:     🟢 LONG

  ENTRY:      64210.0
  STOP LOSS:  63780.0
  TAKE PROFIT:65510.0
  RISK/REWARD: 1:3.0

  RSI:        28.54
  TREND:      UPTREND
  PATTERN:    Bullish Engulfing
  VOLUME:     Spike 🔥
  BOS:        Yes
  CHOCH:      No

  CONFIDENCE: 77%
  SCORE:      7
  RESISTANCE: 64800.0, 65200.0
  SUPPORT:    63900.0, 63500.0
============================================================
```

---

## Signal Scoring System

| Condition                         | Score  |
|-----------------------------------|--------|
| RSI < 30 (oversold)               | +2     |
| RSI > 70 (overbought)             | −2     |
| EMA 9 crosses above EMA 21        | +2     |
| EMA 9 crosses below EMA 21        | −2     |
| MACD bullish crossover            | +1     |
| MACD bearish crossover            | −1     |
| Bullish candlestick pattern       | +3     |
| Bearish candlestick pattern       | −3     |
| Volume spike                      | +1     |
| Market structure UPTREND          | +2     |
| Market structure DOWNTREND        | −2     |
| BOS in trend direction            | ±1     |
| CHOCH (reversal signal)           | ∓1     |
| Price above VWAP                  | +1     |
| Price below VWAP                  | −1     |
| Price outside Bollinger Band      | ±1     |
| Stochastic oversold/overbought    | ±1     |

**Decision:**
- Score ≥ 6 → **LONG**
- Score ≤ −6 → **SHORT**
- Otherwise → **NO TRADE**

---

## Future Extensions

The modular architecture is designed to easily support:

- **Telegram alerts** – add a `notifications/telegram.py` module
- **Web dashboard** – integrate FastAPI + React
- **Backtesting engine** – replay historical OHLCV data through the pipeline
- **AI signal scoring** – replace or augment the scoring system with ML models
- **Order block detection** – extend `market_structure.py`
- **Liquidity grab detection** – detect stop-hunt wicks
- **Whale tracking** – on-chain data integration
- **Futures metrics** – funding rate, open interest via exchange APIs

---

## Disclaimer

This software is for **educational and informational purposes only**.
It does **not** execute trades and **does not** constitute financial advice.
Always do your own research before making investment decisions.
