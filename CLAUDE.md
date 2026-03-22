# CLAUDE.md — StockPortfolioManager

This file provides AI assistants with a comprehensive guide to the codebase: architecture, conventions, workflows, and known issues.

---

## Project Overview

A Python-based personal stock portfolio management system with:
- **Flask REST API** backend (`server.py`) — port 5001
- **React** frontend (`StockManagerWeb/`) — separate repo, connects to this API
- **SQLite** database (`core.db`) for persistent storage
- Support for multi-currency portfolios, multiple data sources (Yahoo Finance, Romanian BVB exchange)
- Dockerised for both development and production (`Dockerfile`, `Dockerfile.dev`, `docker-compose.yml`, `docker-compose.dev.yml`)
- `requirements.txt` present — install with `pip install -r requirements.txt`

---

## Repository Structure

```
StockPortfolioManager/
├── server.py               # Flask API server (28 endpoints, background data fetching)
├── core.db                 # SQLite database (do NOT commit changes to this file)
├── requirements.txt        # Python dependencies
├── test.ipynb              # Jupyter notebook for ad-hoc testing
├── Dockerfile              # Production Docker image
├── Dockerfile.dev          # Development Docker image
├── docker-compose.yml      # Production compose
├── docker-compose.dev.yml  # Development compose
├── backend/
│   ├── __init__.py
│   ├── api.py              # Portfolio analytics — PortfolioStats + Metric subclasses (~409 lines)
│   ├── base.py             # DB abstraction — BaseDBConnector, TableHandler, DataFetcher (86 lines)
│   ├── ticker_fetcher.py   # Stock price fetching — Yahoo Finance / BVB (~109 lines)
│   ├── fx_fetcher.py       # FX rate fetching — Yahoo Finance
│   ├── misc_fetcher.py     # Portfolio read queries — composition, transactions, dividends (69 lines)
│   ├── benchmarks.py       # Benchmark comparison, risk metrics, analytics classes (~999 lines)
│   ├── benchmark_fetcher.py# Fetches and caches benchmark prices in BENCHMARK_PRICES table (108 lines)
│   ├── reporting.py        # Portfolio summary reporting helpers
│   └── sql/
│       ├── __init__.py
│       └── queries.py      # All SQL query strings (279 lines)
├── utils/
│   ├── __init__.py
│   └── utils.py            # Date/time utility functions
└── data_backup/
    ├── db_backup_*.sql     # Historical database backups
    ├── TRANSACTION.csv
    ├── backup.csv
    └── ref_*.csv           # Platform reference data
```

---

## Architecture

### Data Flow

```
React UI (StockManagerWeb, :3000)
    │  HTTP requests
    ▼
Flask API (:5001)
    ├── PortfolioStats       ← in-memory analytics calculations
    ├── MiscFetcher          ← database read queries
    ├── TickerFetcher        ← price data (YF/BVB)
    ├── FxFetcher            ← exchange rates (YF)
    ├── benchmarks.py        ← benchmark comparison, risk metrics, diversification, health score
    └── SQLite (core.db)
         ├── TRANSACTION
         ├── SECURITY
         ├── SECURITY_VALUES
         ├── DIVIDEND
         ├── FX
         ├── FX_CD
         └── BENCHMARK_PRICES   ← cached benchmark index prices

Background Thread (server.py, on startup):
    Fetches missing price/FX/benchmark data for all securities
```

### Key Classes

| Class | File | Responsibility |
|-------|------|----------------|
| `BaseDBConnector` | `backend/base.py` | SQLite connection management, read/write ops |
| `TableHandler` | `backend/base.py` | Per-table CRUD operations |
| `DataFetcher` | `backend/base.py` | Base class for all fetchers |
| `PortfolioStats` | `backend/api.py` | Core analytics: NAV, cost basis, profit, allocation |
| `Period` | `backend/api.py` | Time period calculations (YTD, 1M, 1Y, 3Y, 5Y, ALL) |
| `TickerFetcher` | `backend/ticker_fetcher.py` | Fetches OHLC from YF or BVB web scraping |
| `FxFetcher` | `backend/fx_fetcher.py` | Fetches FX rates from Yahoo Finance |
| `MiscFetcher` | `backend/misc_fetcher.py` | Queries portfolio composition, transactions, dividends |
| `BenchmarkFetcher` | `backend/benchmark_fetcher.py` | Fetches & caches benchmark prices in DB |
| `PortfolioBenchmark` | `backend/benchmarks.py` | Money-weighted portfolio vs benchmark comparison |
| `RiskMetrics` | `backend/benchmarks.py` | Sharpe, Sortino, Volatility, Drawdown, Beta, Alpha, Calmar, Treynor |
| `DiversificationAnalytics` | `backend/benchmarks.py` | HHI, concentration, correlation matrix |
| `DividendAnalytics` | `backend/benchmarks.py` | Annual dividend summary, yield on cost |
| `RebalancingSuggestions` | `backend/benchmarks.py` | Equal-weight and custom target rebalancing |
| `PortfolioHealthScore` | `backend/benchmarks.py` | Composite 0–100 score with grade |
| `InvestmentInsights` | `backend/benchmarks.py` | Actionable insights based on portfolio analysis |

### Metric Subclasses (`backend/api.py`)

All metrics follow a shared pattern — instantiate with relevant params, call `.compute()`:

- `Nav`, `CostBasis`, `Fee`, `Profit`
- `DivYield`, `DivVal`
- `PeriodProfitVal`, `PeriodProfitPerc`
- `PE` (P/E ratio from YF or BVB scraping)
- `DivSecurity`, `CostBasisSecurity`, `EquityGainSecurity`, `EquityAmtSecurity`

### Benchmark Comparison Methodology

`PortfolioBenchmark.compare_performance()` uses a **PeriodProfitPerc-style** approach:

- **Portfolio return at T** = `(profit(T) - profit(start)) / cost(T)` — the change in profit (pure market gain, cancels new capital additions) as % of current cost basis. Mirrors how `PeriodProfitPerc` works.
- **Benchmark return at T** = `bench_price(T) / bench_price(start) - 1` — simple cumulative % from the same start date.

This ensures new BUY transactions don't inflate the portfolio return figure, making the comparison fair for a DCA portfolio.

---

## Database Schema

### TRANSACTION
| Column | Type | Notes |
|--------|------|-------|
| ID | PK | Auto-increment |
| TICKER | TEXT | Stock symbol |
| AMOUNT | REAL | Shares — **negative for SELL** |
| PRICE | REAL | Price per share in the stock's native currency |
| FEE | REAL | Transaction fee |
| FX | REAL | Exchange rate to RON at time of purchase |
| DATE | TEXT | YYYY-MM-DD |
| KIND | TEXT | BUY or SELL |

> **Important:** `AMOUNT` is stored as negative for SELL transactions. `FX` is a numeric exchange rate (not a currency code), used in `AMOUNT * PRICE * FX` to compute the RON total.

### SECURITY
| Column | Type | Notes |
|--------|------|-------|
| TICKER | PK | Stock symbol |
| SECTOR | TEXT | Industry sector |
| COUNTRY | TEXT | Country of listing |
| FX | TEXT | Currency code (e.g. USD, RON) |
| MARKET | TEXT | Exchange market |
| SRC | TEXT | Data source: YF, BVB, or MANUAL |

### SECURITY_VALUES
| Column | Type | Notes |
|--------|------|-------|
| TICKER | TEXT | |
| DATE | TEXT (PK) | YYYY-MM-DD |
| OPEN | REAL | |
| LOW | REAL | |
| HIGH | REAL | |
| CLOSE | REAL | Closing price |

### DIVIDEND
| Column | Type | Notes |
|--------|------|-------|
| ID | PK | Auto-increment |
| PORTFOLIO_ID | TEXT | |
| TICKER | TEXT | |
| AMOUNT | REAL | Dividend amount |
| FX | TEXT | Currency code |
| DATE | TEXT | YYYY-MM-DD |

### FX
| Column | Type | Notes |
|--------|------|-------|
| CURRENCY_CD | TEXT | Currency code |
| DATE | TEXT | YYYY-MM-DD |
| VALUE | REAL | Exchange rate to RON |

### FX_CD
| Column | Type | Notes |
|--------|------|-------|
| FX | TEXT | Symbol (e.g., EURUSD=X) |
| CURRENCY_CD | TEXT | Code (e.g., EUR) |

### BENCHMARK_PRICES
| Column | Type | Notes |
|--------|------|-------|
| TICKER | TEXT (PK) | Benchmark ticker (e.g. SPY) |
| DATE | TEXT (PK) | YYYY-MM-DD |
| CLOSE | REAL | Closing price |

---

## API Endpoints (`server.py`)

All endpoints served on port 5001. CORS is enabled globally.

| Route | Method | Key Query Params | Description |
|-------|--------|-----------------|-------------|
| `/` | GET | — | Health check |
| `/health` | GET | — | DB connectivity check |
| `/dashboard` | GET | — | Key metrics snapshot (NAV, profit, top gainers/losers) |
| `/portfolio` | GET | `ref_date` | Portfolio snapshot at a given date |
| `/performance` | GET | `start_date`, `end_date`, `step`, `kind`, `filters`, `filter_kind`, `default_interval` | Time-series profit |
| `/performance_split` | GET | `start_date`, `end_date`, `step` | Per-ticker profit over time |
| `/composition` | GET | `ref_date`, `hue` | Breakdown by TICKER/COUNTRY/SECTOR/FX |
| `/portfolio_stats` | GET | — | Comprehensive metrics using current date |
| `/security_info` | GET | `security`, `hue`, `dt` | Single security details |
| `/activity` | GET | `ticker`, `filter_kind` | Transaction and dividend history |
| `/metric` | GET | `metric`, `period`, `ticker`, `filter_kind`, `ref_dt` | Computed metric value |
| `/last_trans` | GET | `ticker`, `cnt` | Most recent N transactions |
| `/last_dividends` | GET | `ticker`, `cnt` | Most recent N dividends |
| `/new_transaction` | POST | JSON body | Insert a new transaction |
| `/new_dividend` | POST | JSON body | Insert a new dividend |
| `/new_quote` | POST | JSON body | Add a new security + quote |
| `/benchmark` | GET | `benchmark`, `start_date`, `end_date`, `step`, `default_interval`, `filters`, `filter_kind` | Portfolio vs single benchmark (money-weighted) |
| `/benchmark_multi` | GET | `benchmarks`, `start_date`, `end_date`, `step` | Portfolio vs multiple benchmarks (summary only) |
| `/risk_metrics` | GET | `start_date`, `end_date`, `step`, `benchmark`, `risk_free_rate`, `default_interval` | Sharpe, Sortino, Vol, Drawdown, Beta, Alpha, Calmar, Treynor |
| `/diversification` | GET | `ref_date`, `hue`, `filters`, `filter_kind` | HHI and concentration analysis |
| `/correlation` | GET | `ref_date`, `period_days`, `step` | Pairwise ticker correlation matrix |
| `/dividends_analysis` | GET | — | Annual dividend summary, by-ticker, yield on cost |
| `/rebalance` | GET | `ref_date`, `hue`, `tolerance` | Equal-weight rebalancing suggestions |
| `/rebalance_custom` | POST | JSON body | Custom target rebalancing suggestions |
| `/health_score` | GET | `ref_date`, `period` | Portfolio health score (0–100) with grade |
| `/insights` | GET | `ref_date` | Actionable investment insights |
| `/available_benchmarks` | GET | — | List available benchmark tickers |

### `default_interval` param

`/performance`, `/benchmark`, and `/risk_metrics` all accept `default_interval` (e.g. `1W`, `1M`, `1Q`, `6M`, `1Y`, `YTD`, `3Y`, `5Y`) as a shorthand for setting `start_date` relative to today. Handled by `get_delta_from_interval()` in `server.py`.

### POST Body Schemas

**`/new_transaction`**
```json
{ "ticker": "AAPL", "amount": 10, "price": 150.0, "fee": 1.5, "fx": 4.5, "date": "2024-01-15", "kind": "BUY" }
```

**`/new_dividend`**
```json
{ "ticker": "AAPL", "amount": 25.0, "fx": 4.5, "date": "2024-03-01" }
```

**`/new_quote`**
```json
{ "ticker": "XYZ", "sector": "Technology", "country": "US", "fx": "USD", "market": "NASDAQ", "src": "YF" }
```

---

## Running the Application

```bash
pip install -r requirements.txt
python server.py
```

Backend runs on `http://0.0.0.0:5001`.

### Docker

```bash
# Development
docker-compose -f docker-compose.dev.yml up

# Production
docker-compose up
```

---

## Background Data Fetch

On startup, `server.py` spawns a background thread that:
1. Calls `TickerFetcher.fetch_ticker_hist()` — fetches missing OHLC data for all securities
2. Calls `FxFetcher.fetch_missing_fx()` — fetches missing FX rates
3. Calls `BenchmarkFetcher.fetch_missing()` — fetches missing prices for SPY, QQQ, IWM, EFA, GLD, AGG into `BENCHMARK_PRICES`

Error handling: each fetch loop uses `continue` after exceptions so one failed ticker does not abort the whole batch.

---

## Code Conventions

### Naming
- **snake_case** — functions and variables
- **PascalCase** — class names
- **UPPERCASE** — constants and database column names
- SQL table and column names are always UPPERCASE

### Dates
- All dates stored and passed as strings in `YYYY-MM-DD` format
- Use `utils/utils.py` helpers for date arithmetic

### Filtering Pattern
Many API endpoints accept `filter_kind` (e.g., `TICKER`, `COUNTRY`, `SECTOR`, `FX`) along with a `filters` value to scope results. This pattern is consistent across `PortfolioStats`, `MiscFetcher`, and API routes.

### Metric Computation Pattern
```python
metric = MetricClass(param1, param2, ...)
result = metric.compute()
```

### Data Sources
Securities use a `SRC` field to indicate their data source:
- `YF` — Yahoo Finance (via `yfinance` library)
- `BVB` — Romanian Stock Exchange (via BeautifulSoup web scraping)
- `MANUAL` — Manually entered, no automatic price fetching

---

## Development Workflow

### Branching
- Feature branches use the format `claude/<feature-name>` or `fix/<issue>`
- Never push directly to `main`

### Making Changes
1. Create a feature branch off `main`
2. Read relevant files before modifying them
3. Test via `test.ipynb` or direct API calls (no automated test suite)
4. Commit with descriptive messages
5. Push and open a PR against `main`
6. Update this CLAUDE.md to reflect significant changes

---

## Known Issues and Technical Debt

1. **SQL injection risk** — Many queries use `.format()` string interpolation rather than parameterised queries; be careful when accepting user input
2. **Mixed logging** — `server.py` uses the `logging` module but `backend/` modules still use `print()`
3. **Bare `except` clauses** — Some error handling in fetchers silently swallows exceptions (only prints)
4. **No authentication** — API has no auth layer; CORS is open to all origins
5. **No database migrations** — Schema changes require manual SQL execution
6. **No unit tests** — Only a Jupyter notebook for ad-hoc verification
7. **Romanian-specific defaults** — RON (Romanian leu) is assumed as the base/local currency in FX calculations
8. **`PortfolioStats` inner join drops missing prices** — `pd.merge(..., how='inner')` silently excludes tickers with no price data on a given date, understating NAV for historical dates

---

## Important Files Quick Reference

| File | Lines | What to look at |
|------|-------|-----------------|
| `server.py` | 556 | All API route handlers, background fetch setup, `get_delta_from_interval` |
| `backend/api.py` | 409 | `PortfolioStats` class and all `Metric` subclasses |
| `backend/benchmarks.py` | 999 | `PortfolioBenchmark`, `RiskMetrics`, `DiversificationAnalytics`, `DividendAnalytics`, `RebalancingSuggestions`, `PortfolioHealthScore`, `InvestmentInsights` |
| `backend/benchmark_fetcher.py` | 108 | `BenchmarkFetcher` — caches benchmark prices in `BENCHMARK_PRICES` |
| `backend/base.py` | 86 | DB connection layer — used by all fetchers |
| `backend/sql/queries.py` | 279 | All raw SQL — start here for query changes |
| `backend/misc_fetcher.py` | 69 | Portfolio read queries (composition, transactions) |
| `backend/ticker_fetcher.py` | 109 | Price data fetching logic (YF + BVB scraping) |
