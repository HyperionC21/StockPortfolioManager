"""
Fetches Romania CPI time series and stores it in ROMANIA_CPI.

Normalization rule:
- CPI100 is rebased so that CPI = 100 at the portfolio oldest transaction date.
"""

from datetime import datetime
from typing import Optional

import pandas as pd
import requests

from . import base

WORLD_BANK_CPI_URL = 'https://api.worldbank.org/v2/country/ROU/indicator/FP.CPI.TOTL?format=json&per_page=20000'

_CREATE_TABLE_SQL = '''
    CREATE TABLE IF NOT EXISTS ROMANIA_CPI (
        DATE   TEXT PRIMARY KEY,
        CPI    REAL NOT NULL,
        CPI100 REAL NOT NULL
    )
'''


class InflationFetcher:
    def __init__(self, db_conn: base.BaseDBConnector):
        self.db_conn = db_conn
        self._ensure_table()

    def _ensure_table(self):
        self.db_conn._conn.execute(_CREATE_TABLE_SQL)
        self.db_conn._conn.commit()

    def _oldest_transaction_date(self):
        try:
            df = self.db_conn.read_query(
                "SELECT MIN(DATE(DATE)) as FST_DT FROM `TRANSACTION`"
            )
            val = df['FST_DT'].iloc[0]
            return val if val else None
        except Exception:
            return None

    def _fetch_romania_cpi(self):
        resp = requests.get(WORLD_BANK_CPI_URL, timeout=30)
        resp.raise_for_status()

        payload = resp.json()
        if not isinstance(payload, list) or len(payload) < 2:
            return pd.DataFrame(columns=['DATE', 'CPI'])

        obs = payload[1]
        if not isinstance(obs, list):
            return pd.DataFrame(columns=['DATE', 'CPI'])

        df = pd.DataFrame(obs)
        if 'date' not in df.columns or 'value' not in df.columns:
            return pd.DataFrame(columns=['DATE', 'CPI'])

        # World Bank CPI is annual; represent each value at year-end so it can be aligned on chart dates.
        df = df[['date', 'value']].copy()
        df.rename(columns={'date': 'YEAR', 'value': 'CPI'}, inplace=True)
        df['DATE'] = pd.to_datetime(df['YEAR'].astype(str) + '-12-31', errors='coerce')
        df['CPI'] = pd.to_numeric(df['CPI'], errors='coerce')
        df = df.dropna(subset=['DATE', 'CPI'])
        df = df.sort_values('DATE').reset_index(drop=True)
        return df[['DATE', 'CPI']]

    def fetch_and_store(self, end_date: Optional[str] = None):
        base_date = self._oldest_transaction_date()
        if not base_date:
            print('No transactions found; skipping Romania CPI fetch')
            return

        end_ts = pd.to_datetime(end_date or datetime.now().strftime('%Y-%m-%d'))
        base_ts = pd.to_datetime(base_date)

        df = self._fetch_romania_cpi()
        if df.empty:
            print('Romania CPI source returned no data')
            return

        # Keep data up to requested end date.
        df = df[df['DATE'] <= end_ts].copy()
        if df.empty:
            print('Romania CPI has no observations in requested range')
            return

        # Anchor CPI100 at the latest available CPI observation on/before oldest transaction date.
        anchor_rows = df[df['DATE'] <= base_ts]
        if anchor_rows.empty:
            anchor_cpi = float(df['CPI'].iloc[0])
            print('Oldest transaction predates CPI history; anchoring at first CPI observation')
        else:
            anchor_cpi = float(anchor_rows['CPI'].iloc[-1])

        if anchor_cpi == 0:
            print('Anchor CPI is zero; skipping Romania CPI insert')
            return

        df['CPI100'] = (df['CPI'] / anchor_cpi) * 100.0
        df['DATE'] = df['DATE'].dt.strftime('%Y-%m-%d')

        # Store only from the first transaction date onward for portfolio relevance.
        df = df[df['DATE'] >= base_date].copy()

        # Ensure an explicit anchor row at base_date with CPI100=100.
        if not (df['DATE'] == base_date).any():
            anchor_row = pd.DataFrame([
                {'DATE': base_date, 'CPI': anchor_cpi, 'CPI100': 100.0}
            ])
            df = pd.concat([anchor_row, df], ignore_index=True)

        df = df.drop_duplicates(subset=['DATE'], keep='last').sort_values('DATE').reset_index(drop=True)

        for _, row in df[['DATE', 'CPI', 'CPI100']].iterrows():
            self.db_conn._conn.execute(
                'INSERT OR REPLACE INTO ROMANIA_CPI (DATE, CPI, CPI100) VALUES (?, ?, ?)',
                (row['DATE'], float(row['CPI']), float(row['CPI100']))
            )
        self.db_conn._conn.commit()

        print(f'Stored {len(df)} Romania CPI rows (base date {base_date} = 100)')

    def get_series(self, start_date: str, end_date: str):
        return self.db_conn.read_query(f'''
            SELECT DATE, CPI, CPI100
            FROM ROMANIA_CPI
            WHERE DATE >= '{start_date}'
              AND DATE <= '{end_date}'
            ORDER BY DATE
        ''')
