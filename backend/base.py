import pandas as pd
import sqlite3
import pandas as pd
import yfinance as yf
from datetime import datetime

class BaseDBConnector:
    def __init__(self, db_path):
        self._conn = sqlite3.connect(db_path)
    
    def insert_data(self, df, table_name):
        df.to_sql(table_name, if_exists='append', con=self._conn, index=False)
        self._conn.commit()
    
    def check_table(self, table_name):
        query = f'''
            SELECT * FROM {table_name} WHERE 1=3
        '''

        df = None 
        try:
            df = pd.read_sql(query, self._conn)
        except:
            return None
        
        return df

    def read_table(self, table_name):
        query = f'''
            SELECT * FROM {table_name}
        '''

        return pd.read_sql(query, self._conn)
    
    def read_query(self, query):
        return pd.read_sql(query, self._conn)



class TableHandler:
    def __init__(self, db_connector, table_name, pk) -> None:
        self._db_connector = db_connector
        self._pk = pk
        self.table_name = table_name
        
        query = f'''
            SELECT * FROM '{table_name}' WHERE 1 = 3
        '''

        df = self._db_connector.read_query(query)

        self.table_fields = list(df.columns)


    def get_val(self, pk_val):
        try:
            query = f'''
                SELECT * FROM {self.table_name} WHERE {self._pk} = '{pk_val}'
            '''

            row = self._db_connector.read_query(query)

            return row
        except:
            raise Exception('Failed to get value')
    
    def insert_val(self, data : dict):
        data_cols = set(data.keys())

        df = pd.DataFrame.from_dict(data)

        self._db_connector.insert_data(df, self.table_name)
    
    def load_csv(self, f_path):
        data = pd.read_csv(f_path).to_dict(orient='list')
        self.insert_val(data)

class DataFetcher:
    def __init__(self, db_conn):
        self.db_conn = db_conn
    
    def fetch_ticker_prices(self, tickers, ref_date):
        query = f'''
            SELECT
                t1.TICKER,
                t1.CLOSE as PRICE 
            FROM
                `SECURITY_VALUES` as t1
            INNER JOIN
            (
                SELECT
                    TICKER,
                    MAX(DATE(DATE)) as "DATE"
                FROM
                    `SECURITY_VALUES`
                WHERE
                    DATE(DATE) <= DATE('{ref_date}')
                GROUP BY
                    TICKER
            ) t2
            ON t1.TICKER = t2.TICKER AND DATE(t1.DATE) = DATE(t2.DATE)
            WHERE
                1 = 1
                AND t1.TICKER IN ({",".join(tickers)}) '''

        ticker_prices = self.db_conn.read_query(query)

        return ticker_prices

    def fetch_fx_val(self, fxs, ref_date):
        query = f'''
            SELECT
                CURRENCY_CD,
                VALUE
            FROM
            (
                SELECT
                    t1.CURRENCY_CD,
                    t1.VALUE,
                    t1.DATE,
                    RANK() OVER (PARTITION BY t1.CURRENCY_CD ORDER BY t1.DATE DESC) as RNK
                FROM
                    FX t1
                WHERE
                    1 = 1
            )
            WHERE
                1 = 1
                AND RNK = 1
            '''
        return self.db_conn.read_query(query)

    def fetch_ticker_fx(self, tickers, ref_date):
        pass

    def fetch_fst_trans_date_per_ticker(self):
        query = f'''
            SELECT
                t1.TICKER,
                MIN(DATE(t1.DATE)) as "FST_BUY_DT"
            FROM
                'TRANSACTION' t1
            WHERE
                1 = 1
            GROUP BY
                t1.TICKER
        '''

        fst_dt = self.db_conn.read_query(query)

        return fst_dt 
    
    def fetch_fst_trans(self):
        query = f'''
            SELECT
                MIN(DATE(t1.DATE)) as "FST_BUY_DT"
            FROM
                'TRANSACTION' t1
        '''

        fst_dt = self.db_conn.read_query(query)

        return fst_dt

    def fetch_currencies(self):
        query = f'''
            SELECT
                FX,
                CURRENCY_CD 
            FROM
                `FX_CD`
            WHERE
                1 = 1
                AND FX <> '#NA'
        '''

        currencies = self.db_conn.read_query(query)

        return currencies

    def fetch_all_transacted_tickers(self):
        query = f'''
            SELECT DISTINCT 
                t1.TICKER
            FROM `TRANSACTION` as t1
            INNER JOIN `SECURITY` as t2 ON t1.TICKER = t2.TICKER
            WHERE
                1 = 1
                AND t2.SRC <> 'MANUAL'
        '''

        tickers = self.db_conn.read_query(query)

        return tickers

    def fetch_ticker_hist(self, start_date, end_date):
        
        df_tickers = self.fetch_all_transacted_tickers()

        hists = []
        for _, row in df_tickers.iterrows():
            try:
                ticker = yf.Ticker(row['TICKER'])
                hist = ticker.history(start=start_date, end=end_date).reset_index()
                hist['TICKER'] = row['TICKER']
                hists.append(hist)
            except Exception as e:
                print(e)
                print(f'Ticker {row["TICKER"]} not found on yahoo finance')

        hist = pd.concat(hists, axis=0)
        hist = hist[['TICKER', 'Date', 'Open', 'High', 'Low', 'Close']]
        hist.columns = list(map(lambda x: x.upper(), hist.columns))	

        self.db_conn.insert_data(hist, 'SECURITY_VALUES')

        return hist

    def fetch_fx(self, start_date, end_date):

        currencies = self.fetch_currencies()

        for _, row in currencies.iterrows():
            ticker = yf.Ticker(row['CURRENCY_CD'])
            curr_hist = ticker.history(start=start_date, end=end_date).reset_index()
            curr_hist.columns = list(map(lambda x: x.upper(), curr_hist.columns))	

            curr_hist = curr_hist[['CLOSE', 'DATE']]
            curr_hist.rename(columns={
                'CLOSE' : 'VALUE'
            }, inplace=True)
            curr_hist['CURRENCY_CD'] = row['CURRENCY_CD']

            self.db_conn.insert_data(curr_hist, 'FX')

    def fetch_portfolio_composition(self, portfolio_id : int, ref_date : str):
        query = f'''
            SELECT
                t1.TICKER,
                SUM(t1.AMOUNT) as N_SHARES,
                '{ref_date}' as DT
            FROM
                'TRANSACTION' as t1
            WHERE
                1 = 1
                AND t1.PORTFOLIO_ID = {portfolio_id}
                AND DATE(t1.DATE) < DATE('{ref_date}')
            GROUP BY
                t1.TICKER 
        '''

        df = self.db_conn.read_query(query)
        
        return df