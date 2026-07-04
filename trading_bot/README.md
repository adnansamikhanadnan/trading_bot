# Simplified Trading Bot — Binance Futures Testnet (USDT-M)

A small, dependency-light Python CLI that places MARKET, LIMIT, and (bonus)
STOP_LIMIT orders on Binance Futures Testnet, with structured code,
validation, logging, and error handling.

## Project structure

```
trading_bot/
  bot/
    __init__.py
    client.py          # Signed REST client for Binance Futures API
    orders.py          # Order orchestration (client-agnostic)
    validators.py       # Pure input validation, no network calls
    logging_config.py   # Rotating file + console logging setup
  cli.py                # argparse CLI entry point
  logs/
    trading_bot.log     # Created at runtime; full request/response/error log
  requirements.txt
  .env.example
  README.md
```

**Design notes**

- The API layer (`bot/client.py`) and the CLI layer (`cli.py`) are fully
  separated. `bot/orders.py` sits in between and knows nothing about
  argparse or stdin — it just takes a validated `OrderRequest` and a
  client, and returns a result. This makes each piece independently
  testable and reusable (e.g. from a future web UI or scheduler).
- Implemented with `requests` and manual HMAC-SHA256 signing rather than
  `python-binance`, so the exact signing/error logic is visible and
  auditable rather than hidden inside a third-party library.
- All request params, raw response bodies, and exceptions are logged to
  `logs/trading_bot.log` (rotated at 5MB, 3 backups). The API secret and
  computed signature are never written to the log.

## 1. Setup

### 1.1 Binance Futures Testnet account

1. Go to <https://testnet.binancefuture.com> and log in with a GitHub account.
2. Once logged in, open **API Key** in the account menu and generate a new
   API key + secret. Save both immediately — the secret is shown once.
3. The testnet gives you a virtual USDT-M futures balance automatically;
   no real funds are involved.

### 1.2 Local environment

```bash
git clone <this-repo-url>
cd trading_bot
python3 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### 1.3 Credentials

Copy `.env.example` to `.env` and fill in your testnet key/secret, then
export them into your shell:

```bash
cp .env.example .env
# edit .env with your values, then:
export $(grep -v '^#' .env | xargs)
```

Or simply export directly:

```bash
export BINANCE_API_KEY="your_testnet_api_key"
export BINANCE_API_SECRET="your_testnet_api_secret"
```

Credentials can also be passed explicitly with `--api-key` / `--api-secret`,
but environment variables are recommended so secrets never appear in shell
history.

## 2. Running the bot

### Market order

```bash
python cli.py --symbol BTCUSDT --side BUY --type MARKET --quantity 0.01
```

### Limit order

```bash
python cli.py --symbol BTCUSDT --side SELL --type LIMIT --quantity 0.01 --price 65000
```

### Stop-limit order (bonus order type)

```bash
python cli.py --symbol BTCUSDT --side SELL --type STOP_LIMIT \
  --quantity 0.01 --price 64000 --stop-price 64500
```

### Dry run (validate only, no API call)

Useful for checking your inputs parse correctly before touching the API:

```bash
python cli.py --symbol BTCUSDT --side BUY --type MARKET --quantity 0.01 --dry-run
```

### All CLI options

```bash
python cli.py --help
```

| Flag | Required | Notes |
|---|---|---|
| `--symbol` | yes | e.g. `BTCUSDT` |
| `--side` | yes | `BUY` or `SELL` |
| `--type` | yes | `MARKET`, `LIMIT`, or `STOP_LIMIT` |
| `--quantity` | yes | must be > 0 |
| `--price` | for LIMIT/STOP_LIMIT | must be > 0 |
| `--stop-price` | for STOP_LIMIT | trigger price, must be > 0 |
| `--time-in-force` | no | default `GTC` |
| `--base-url` | no | default `https://testnet.binancefuture.com` |
| `--api-key` / `--api-secret` | no | overrides env vars |
| `--log-level` | no | console verbosity; file log is always DEBUG |
| `--dry-run` | no | validate and print without calling the API |

## 3. Example output

```
Order request:
  symbol=BTCUSDT | side=BUY | type=MARKET | quantity=0.01
Order response:
  orderId=123456789 | status=NEW | executedQty=0.01 | avgPrice=65123.40
✅ Order placed successfully.
```

On failure (e.g. bad input, rejected order, or network issue), the CLI
prints a clear `❌` message and exits with a non-zero status code
(`2` for input/credential problems, `1` for API/network failures), while
the full detail is written to `logs/trading_bot.log`.

## 4. Logging

Every run appends to `logs/trading_bot.log`:

- Every outgoing request (endpoint + params, secrets excluded)
- Every raw response body and HTTP status
- Any validation errors, API errors, or network exceptions, with context

The console only shows a concise summary; the file is the full audit trail.

## 5. Error handling

Three layers are handled distinctly:

1. **Invalid input** (`bot/validators.py`) — e.g. missing price for a LIMIT
   order, non-positive quantity, malformed symbol. Caught before any network
   call is made.
2. **API errors** (`bot/client.py` → `BinanceAPIError`) — any 4xx/5xx response
   from Binance is parsed for its `code`/`msg` and surfaced clearly (e.g.
   insufficient testnet balance, invalid symbol, filter violations).
3. **Network errors** (`bot/client.py` → `BinanceNetworkError`) — timeouts or
   connection failures are caught separately from API errors so the two
   failure modes aren't confused with each other.

## 6. Assumptions

- Binance Futures Testnet's `STOP` order type (stop-limit) is used to
  implement the bonus `STOP_LIMIT` CLI order type; Binance's "stop-limit"
  and "stop" naming differ slightly between spot and futures APIs.
- Quantity/price precision (`stepSize`/`tickSize` per symbol) is **not**
  auto-corrected — the bot passes through what the user provides. Binance's
  `/fapi/v1/order` endpoint will reject values that violate a symbol's
  filters, and the resulting `BinanceAPIError` message will explain why.
  A production version would fetch `/fapi/v1/exchangeInfo` and round
  automatically.
- Only one order is placed per CLI invocation — this matches the task's
  scope of a simple CLI trading tool rather than a persistent bot process.
- `recvWindow` is fixed at 5000ms, Binance's typical default.

## 7. Bonus implemented

- **Third order type**: `STOP_LIMIT` (see above).
- **Dry-run mode** for safe validation without hitting the API.
