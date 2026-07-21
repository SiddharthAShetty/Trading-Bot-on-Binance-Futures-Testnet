# 📈 Binance Futures Testnet Trading Bot

[![Python 3.9+](https://img.shields.io/badge/python-3.9%2B-blue?logo=python)](https://python.org)
[![Binance Testnet](https://img.shields.io/badge/Binance-Testnet%20USDT--M-yellow?logo=binance)](https://testnet.binancefuture.com)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

A clean, production-grade CLI trading bot for Binance Futures Testnet (USDT-M).  
Places **Market**, **Limit**, **Stop-Limit**, and **TWAP** orders with structured JSON logging, full input validation, and a beautiful Rich terminal UI.

---

## ✨ Features

| Feature | Details |
|---------|---------|
| **4 Order Types** | Market, Limit, Stop-Limit, TWAP (bonus) |
| **BUY & SELL** | Full side support |
| **Rich TUI** | Color-coded tables, spinners, progress bars |
| **Interactive Wizard** | Guided `interactive` command for quick ad-hoc orders |
| **Dry-run mode** | `--dry-run` flag previews any order without API calls |
| **Structured Logging** | One JSON object per line in `logs/trading_bot.log` |
| **Input Validation** | Catches bad symbols, quantities, prices *before* hitting the API |
| **Error Handling** | API errors, network failures, and timeouts — all handled gracefully |
| **Server-Time Sync** | Auto-syncs clock offset to avoid timestamp errors |
| **Layered Architecture** | `client` → `orders` → `validators` → `cli` — fully separated |

---

## 🏗 Project Structure

```
trading_bot/
├── bot/
│   ├── __init__.py
│   ├── client.py          # Binance REST client (signing, retries, error parsing)
│   ├── orders.py          # Order placement logic (market, limit, stop-limit, TWAP)
│   ├── validators.py      # Input validation — raises clear errors before any API call
│   └── logging_config.py  # JSON file logging + optional console handler
├── logs/
│   └── trading_bot.log    # Structured JSON logs (auto-created)
├── cli.py                 # Click CLI entry point with Rich UI
├── .env.example           # Credential template
├── requirements.txt
└── README.md
```

---

## 🚀 Setup

### 1. Prerequisites

- Python 3.9 or later
- A [Binance Futures Testnet](https://testnet.binancefuture.com) account

### 2. Get Testnet API Credentials

1. Go to [testnet.binancefuture.com](https://testnet.binancefuture.com)  and log in/create your account
2. From the top navigation bar:
   - Click **Trade**
   - Select **Demo Trading**
3. Once the Demo Trading dashboard opens:
   - Click your **Profile icon** in the top-right corner
   - Select **Demo Trading API**
4. Click **Create API**
5. Generate and copy your:
   - **API Key**
   - **Secret Key**
6. Save these keys securely. You will use them in your project configuration.

### 3. Clone & Install

```bash
git clone https://github.com/SiddharthAShetty/trading-bot.git
cd trading-bot

python -m venv venv
source venv/bin/activate       # Windows: ./venv/Scripts/activate

pip install -r requirements.txt
```

### 4. Configure Credentials

```bash
copy .env.example .env
```

Edit `.env`:

```env
BINANCE_API_KEY=your_testnet_api_key
BINANCE_API_SECRET=your_testnet_api_secret
```

> **Security note:** `.env` is gitignored by default. Never commit real credentials.

---

## 💻 Usage

All commands live under `python cli.py`. Run `--help` on any for full options.

### Market Order

```bash
# Buy 0.001 BTC at market price
python cli.py market --symbol BTCUSDT --side BUY --quantity 0.001

# Sell 0.1 ETH at market price
python cli.py market --symbol ETHUSDT --side SELL --quantity 0.1
```

### Limit Order

```bash
# Buy 0.001 BTC at $60,000 (GTC)
python cli.py limit --symbol BTCUSDT --side BUY --quantity 0.001 --price 60000

# Sell 0.5 ETH at $3,500 (Fill-or-Kill)
python cli.py limit --symbol ETHUSDT --side SELL --quantity 0.5 --price 3500 --tif FOK
```

### Stop-Limit Order *(bonus)*

```bash
# Sell 0.001 BTC: triggers at $61,000, executes at $60,500
python cli.py stop-limit \
  --symbol BTCUSDT \
  --side SELL \
  --quantity 0.001 \
  --stop-price 61000 \
  --price 60500
```

### TWAP Order *(bonus)*

```bash
# Buy 0.005 BTC split across 5 slices, 10 seconds apart
python cli.py twap \
  --symbol BTCUSDT \
  --side BUY \
  --quantity 0.005 \
  --slices 5 \
  --interval 10
```

### Interactive Wizard

```bash
# Guided prompts for all fields — great for exploratory use
python cli.py interactive
```

### Dry-Run (no real orders)

```bash
# Preview any order without hitting the API
python cli.py --dry-run market --symbol BTCUSDT --side BUY --quantity 0.001
python cli.py --dry-run twap  --symbol BTCUSDT --side BUY --quantity 0.05 --slices 5 --interval 2
```

---

## 📋 Output Example

```
 ████████╗██████╗  █████╗ ██████╗ ██╗███╗   ██╗ ██████╗
 ╚══██╔══╝██╔══██╗██╔══██╗██╔══██╗██║████╗  ██║██╔════╝
    ██║   ██████╔╝███████║██║  ██║██║██╔██╗ ██║██║  ███╗
    ██║   ██╔══██╗██╔══██║██║  ██║██║██║╚██╗██║██║   ██║
    ██║   ██║  ██║██║  ██║██████╔╝██║██║ ╚████║╚██████╔╝
    ╚═╝   ╚═╝  ╚═╝╚═╝  ╚═╝╚═════╝ ╚═╝╚═╝  ╚═══╝ ╚═════╝
            Binance Futures Testnet · USDT-M

╭─────────────────────────────────────╮
│       Order Request Summary          │
├──────────────────┬──────────────────┤
│ Symbol           │ BTCUSDT          │
│ Side             │ BUY              │
│ Order Type       │ MARKET           │
│ Quantity         │ 0.001            │
╰──────────────────┴──────────────────╯

Confirm order? [y/N]: y

⠸ Sending MARKET order…

╭──────────────────────────────────────╮
│  ✅ Order Response                    │
│  Order ID       3819274651           │
│  Symbol         BTCUSDT              │
│  Status         FILLED               │
│  Side           BUY                  │
│  Executed Qty   0.001                │
│  Avg Price      62845.30             │
╰──────────────────────────────────────╯

✓ Market order submitted successfully.
```

---

## 📝 Logging

Every run appends to `logs/trading_bot.log` in structured JSON (one object per line).

```json
{"ts": "2025-05-08T10:00:01.456789+00:00", "level": "INFO", "logger": "trading_bot.orders", "message": "MARKET order placed", "orderId": 3819274651, "status": "FILLED"}
{"ts": "2025-05-08T10:00:01.789012+00:00", "level": "ERROR", "logger": "trading_bot.client", "message": "API error", "code": -1121, "message": "Invalid symbol."}
```

Benefits of JSON logs:
- **grep-able** — `grep '"level": "ERROR"' logs/trading_bot.log`
- **jq-friendly** — `jq 'select(.level=="ERROR")' logs/trading_bot.log`
- **Audit trail** — every request, response, and error is recorded

---

## ⚙️ Architecture

```
User Input (CLI)
      │
      ▼
cli.py  ─── validates via validators.py
      │
      ▼
orders.py  ─── builds request payload per order type
      │
      ▼
client.py  ─── signs, timestamps, retries, logs
      │
      ▼
Binance Futures REST API (testnet)
```

**Key design decisions:**

- `client.py` knows nothing about order types — it only signs and sends.
- `orders.py` knows nothing about the CLI — it only builds payloads.
- `validators.py` runs before any network call, giving fast and clear user feedback.
- `cli.py` handles only presentation (Rich UI, prompts, confirmations).

---

## 🔧 Configuration Reference

| Env Variable | Required | Description |
|---|---|---|
| `BINANCE_API_KEY` | ✅ | Testnet API key |
| `BINANCE_API_SECRET` | ✅ | Testnet API secret |

| CLI Flag | Default | Description |
|---|---|---|
| `--dry-run` | `False` | Simulate order, no API call |
| `--log-level` | `DEBUG` | Logging verbosity (`DEBUG`/`INFO`/`WARNING`) |

---

## 🧪 TWAP Explained

TWAP (Time-Weighted Average Price) is a common institutional execution strategy.  
It splits a large order into smaller slices to minimize market impact and achieve a price close to the time-weighted average.

```
Total: 0.005 BTC   Slices: 5   Interval: 10s

T=0s   →  Market BUY 0.001 BTC @ 62,845
T=10s  →  Market BUY 0.001 BTC @ 62,901
T=20s  →  Market BUY 0.001 BTC @ 62,878
T=30s  →  Market BUY 0.001 BTC @ 62,834
T=40s  →  Market BUY 0.001 BTC @ 62,860

Avg executed price:  62,863.6
```

---

## Assumptions

1. **Testnet only** — base URL is hardcoded to `https://testnet.binancefuture.com`. Change `BASE_URL` in `client.py` to go live (with caution).
2. **USDT-M futures** — all orders target the USDT-margined futures market.
3. **No position management** — this bot places orders only; it does not track open positions or PnL.
4. **Quantity precision** — the bot uses 3 decimal places. Some symbols (e.g. BTCUSDT) require specific step sizes; if you hit a `-1111` filter error, adjust quantity precision accordingly.
5. **TWAP is synchronous** — the CLI blocks during TWAP execution. For production use, this should run as an async background task.

---

## License

MIT — free to use, modify, and distribute.
