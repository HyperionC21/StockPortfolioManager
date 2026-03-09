"""
Fetches and caches benchmark index prices in the BENCHMARK_PRICES table.

Runs as part of the background data fetch on startup so that benchmark
comparison and risk metric endpoints read from the DB rather than calling
Yahoo Finance on every request.
"""

import time
import pandas as pd
import yfinance as yf
from utils import utils
from datetime import datetime
from . import base

# Tickers shown in the BenchmarkChart UI selector
BENCHMARK_TICKERS = ['SPY', 'QQQ', 'IWM', 'EFA', 'GLD', 'AGG']

_CREATE_TABLE_SQL = '''
    CREATE TABLE IF NOT EXISTS BENCHMARK_PRICES (
        TICKER TEXT NOT NULL,
        DATE   TEXT NOT NULL,
        CLOSE  REAL,
        PRIMARY KEY (TICKER, DATE)
    )
'''


class BenchmarkFetcher:
    def __init__(self, db_conn: base.BaseDBConnector):
        self.db_conn = db_conn
        self._ensure_table()

    def _ensure_table(self):
        self.db_conn._conn.execute(_CREATE_TABLE_SQL)
        self.db_conn._conn.commit()

    def _last_stored_date(self, ticker: str):
        """Return the latest DATE we have for this ticker, or None."""
        try:
            df = self.db_conn.read_query(
                f"SELECT MAX(DATE) as D FROM BENCHMARK_PRICES WHERE TICKER = '{ticker}'"
            )
            val = df['D'].iloc[0]
            return val if val else None
        except Exception:
            return None

    def fetch_missing(self, start_date: str, end_date: str):
        """Fetch and store any missing benchmark price data."""
        for ticker in BENCHMARK_TICKERS:
            last = self._last_stored_date(ticker)
            fetch_from = last if last and last > start_date else start_date

            if fetch_from >= end_date:
                continue

            try:
                time.sleep(0.1)
                t = yf.Ticker(ticker)
                hist = t.history(start=fetch_from, end=end_date)
                if hist.empty:
                    continue

                hist = hist[['Close']].reset_index()
                # Strip timezone from Date if present
                if hasattr(hist['Date'].dtype, 'tz') and hist['Date'].dtype.tz is not None:
                    hist['Date'] = hist['Date'].dt.tz_localize(None)
                hist['DATE'] = hist['Date'].apply(lambda x: x.strftime('%Y-%m-%d'))
                hist['TICKER'] = ticker
                hist['CLOSE'] = hist['Close']

                for _, row in hist[['TICKER', 'DATE', 'CLOSE']].iterrows():
                    self.db_conn._conn.execute(
                        'INSERT OR IGNORE INTO BENCHMARK_PRICES (TICKER, DATE, CLOSE) VALUES (?, ?, ?)',
                        (row['TICKER'], row['DATE'], float(row['CLOSE']))
                    )
                self.db_conn._conn.commit()
                print(f'Stored {len(hist)} rows for benchmark {ticker}')
            except Exception as e:
                print(f'Failed to fetch benchmark {ticker}: {e}')


def get_benchmark_prices_from_db(db_conn: base.BaseDBConnector,
                                  ticker: str,
                                  start_date: str,
                                  end_date: str) -> pd.DataFrame:
    """
    Read benchmark close prices from the DB for the given date range.
    Returns a DataFrame with a datetime index and a 'price' column.
    Returns an empty DataFrame if no data is found.
    """
    try:
        df = db_conn.read_query(f'''
            SELECT DATE, CLOSE as price
            FROM BENCHMARK_PRICES
            WHERE TICKER = '{ticker}'
              AND DATE >= '{start_date}'
              AND DATE <= '{end_date}'
            ORDER BY DATE
        ''')
        if df.empty:
            return pd.DataFrame()
        df['date'] = pd.to_datetime(df['DATE'])
        df = df.set_index('date')[['price']]
        return df
    except Exception:
        return pd.DataFrame()
