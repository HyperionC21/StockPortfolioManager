# CLAUDE.md — StockPortfolioManager

This file provides AI assistants with a comprehensive guide to the codebase: architecture, conventions, workflows, and known issues.

---

## Project Overview

A Python-based personal stock portfolio management system with:
- **Flask REST API** backend (`server.py`) — port 5001
- **Dash/Plotly** interactive frontend (`app.py`) — port 8050
- **SQLite** database (`core.db`) for persistent storage
- Support for multi-currency portfolios, multiple data sources (Yahoo Finance, Romanian BVB exchange)

---

## Repository Structure

```
StockPortfolioManager/
├── app.py                  # Dash frontend (UI components + HTTP calls to Flask)
├── server.py               # Flask API server (14 endpoints, background data fetching)
├── core.db                 # SQLite database (do not commit changes to this file)
├── test.ipynb              # Jupyter notebook for ad-hoc testing
├── out_aapl.json           # Sample output data
├── backend/
│   ├── __init__.py
│   ├── api.py              # Portfolio analytics — PortfolioStats + 15 Metric subclasses
│   ├── base.py             # DB abstraction — BaseDBConnector, TableHandler, DataFetcher
│   ├── ticker_fetcher.py   # Stock price fetching (Yahoo Finance / BVB)
│   ├── fx_fetcher.py       # FX rate fetching (Yahoo Finance)
│   ├── misc_fetcher.py     # Portfolio data queries (composition, transactions, dividends)
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
Dash UI (:8050)
    │  HTTP requests
    ▼
Flask API (:5001)
    ├── PortfolioStats       ← in-memory analytics calculations
    ├── MiscFetcher          ← database read queries
    ├── TickerFetcher        ← price data (YF/BVB)
    ├── FxFetcher            ← exchange rates (YF)
    └── SQLite (core.db)
         ├── TRANSACTION
         ├── SECURITY
         ├── SECURITY_VALUES
         ├── DIVIDEND
         ├── FX
         └── FX_CD

Background Process (server.py):
    Spawns separate process to fetch missing price/FX data on startup
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

### Metric Subclasses (`backend/api.py`)

All metrics follow a shared pattern — instantiate with relevant params, call `.compute()`:

- `Nav`, `CostBasis`, `Fee`, `Profit`
- `DivYield`, `DivVal`
- `PeriodProfitVal`, `PeriodProfitPerc`
- `PE` (P/E ratio from YF or BVB scraping)
- `DivSecurity`, `CostBasisSecurity`, `EquityGainSecurity`, `EquityAmtSecurity`

---

## Database Schema

### TRANSACTION
| Column | Type | Notes |
|--------|------|-------|
| ID | PK | Auto-increment |
| TICKER | TEXT | Stock symbol |
| AMOUNT | REAL | Number of shares |
| PRICE | REAL | Price per share |
| FEE | REAL | Transaction fee |
| FX | TEXT | Currency code |
| DATE | TEXT | YYYY-MM-DD |
| KIND | TEXT | BUY or SELL |

### SECURITY
| Column | Type | Notes |
|--------|------|-------|
| TICKER | PK | Stock symbol |
| SECTOR | TEXT | Industry sector |
| COUNTRY | TEXT | Country of listing |
| FX | TEXT | Currency code |
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

---

## API Endpoints (`server.py`)

All endpoints served on port 5001. CORS is enabled globally.

| Route | Method | Key Query Params | Description |
|-------|--------|-----------------|-------------|
| `/` | GET | — | Health check |
| `/portfolio` | GET | `ref_date` | Portfolio snapshot at a given date |
| `/performance` | GET | `start_date`, `end_date`, `step`, `kind`, `filters`, `filter_kind` | Time-series profit |
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

### POST Body Schemas

**`/new_transaction`**
```json
{ "TICKER": "AAPL", "AMOUNT": 10, "PRICE": 150.0, "FEE": 1.5, "FX": "USD", "DATE": "2024-01-15", "KIND": "BUY" }
```

**`/new_dividend`**
```json
{ "TICKER": "AAPL", "AMOUNT": 25.0, "FX": "USD", "DATE": "2024-03-01" }
```

**`/new_quote`**
```json
{ "TICKER": "XYZ", "SECTOR": "Technology", "COUNTRY": "US", "FX": "USD", "MARKET": "NASDAQ", "SRC": "YF" }
```

---

## Running the Application

There is no requirements.txt. Install dependencies manually:

```bash
pip install flask flask-cors dash plotly yfinance pandas numpy requests beautifulsoup4
```

Start the backend:
```bash
python server.py
```

Start the frontend (in a separate terminal):
```bash
python app.py
```

- Backend: http://127.0.0.1:5001
- Frontend: http://127.0.0.1:8050

> The frontend (`app.py`) is currently hardcoded to connect to `http://127.0.0.1:5000` — note the port mismatch (5000 vs 5001). Verify and align these before running.

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
- Development branches use the format `claude/<feature-name>-<id>`
- Never push directly to `master`

### Making Changes
1. Ensure you are on the correct feature branch
2. Read relevant files before modifying them
3. Run `test.ipynb` cells to verify behavior (no automated test suite)
4. Commit with descriptive messages
5. Push with: `git push -u origin <branch-name>`
6. Update the CLAUDE.md file to reflect the new changes

### No Automated Testing
The only testing is via `test.ipynb`. When making changes:
- Test relevant API endpoints manually or via the notebook
- Verify database reads/writes with direct SQLite queries if needed

---

## Known Issues and Technical Debt

1. **No `requirements.txt`** — Dependencies must be inferred from imports
2. **SQL injection risk** — Many queries use Python string formatting (`.format()`) rather than parameterized queries; treat carefully when accepting user input
3. **Hardcoded paths/URLs** — `core.db` path and `http://127.0.0.1:5000` are hardcoded; port mismatch between app.py (5000) and server.py (5001)
4. **`print` for logging** — No use of the `logging` module; errors and debug info go to stdout
5. **Bare `except` clauses** — Some error handling silently swallows exceptions
6. **No authentication** — API has no auth layer; CORS is open to all origins
7. **No database migrations** — Schema changes require manual SQL execution
8. **No unit tests** — Only a Jupyter notebook for ad-hoc verification
9. **Monolithic `api.py`** — 409 lines handling both analytics logic and all metric subclasses
10. **Romanian-specific defaults** — RON (Romanian leu) is assumed as the base/local currency in FX calculations

---

## Important Files Quick Reference

| File | Lines | What to look at |
|------|-------|-----------------|
| `server.py` | 306 | All API route handlers and background fetch setup |
| `backend/api.py` | 409 | `PortfolioStats` class and all `Metric` subclasses |
| `backend/base.py` | 86 | DB connection layer — used by all fetchers |
| `backend/sql/queries.py` | 279 | All raw SQL — start here for query changes |
| `backend/misc_fetcher.py` | 69 | Portfolio read queries (composition, transactions) |
| `backend/ticker_fetcher.py` | 107 | Price data fetching logic (YF + BVB scraping) |
| `app.py` | 130 | Dash layout and all frontend callbacks |
