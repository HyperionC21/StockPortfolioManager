from utils import utils

import pandas as pd
import sqlite3
import pandas as pd
import yfinance as yf
from datetime import datetime
import requests
import bs4

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
            SELECT * FROM `{table_name}`
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

    def fetch_all_transacted_tickers(self):
        query = f'''
            SELECT DISTINCT 
                t1.TICKER
            FROM `SECURITY` t1
            WHERE
                1 = 1
                AND t1.SRC <> 'MANUAL'
        '''

        return self.db_conn.read_query(query)

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

    def fetch_fx_val(self, ref_date):
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
                    AND DATE(t1.DATE) <= DATE('{ref_date}')
            )
            WHERE
                1 = 1
                AND RNK = 1
            '''
        return self.db_conn.read_query(query)

    def fetch_ticker_fx(self, ref_date):
        tickers = self.fetch_all_transacted_tickers()
        fx_vals = self.fetch_fx_val(ref_date)

        tickers = list(map(lambda x: f"'{x}'", tickers['TICKER']))

        query = f'''
            SELECT
            t1.TICKER,
            t2.CURRENCY_CD
        FROM
            SECURITY t1
        LEFT JOIN
            FX_CD t2 ON t1.FX = t2.FX
        WHERE
            1 = 1
            AND t1.TICKER IN ({','.join(tickers)})
        '''

        tickers_fx = self.db_conn.read_query(query)

        tickers_fx = pd.merge(tickers_fx, fx_vals, on='CURRENCY_CD', how='inner')

        tickers_fx = tickers_fx[['TICKER', 'VALUE']]
        return tickers_fx

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
                SUM(t1.AMOUNT * t1.PRICE * t1.FX) as TOTAL_COST,
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

class DBUpdater(DataFetcher):
    def __init__(self, db_conn):
        super().__init__(db_conn)

    def fetch_missing_fx(self, start_dt, end_dt):
        query = f'''
        SELECT
            t1.CURRENCY_CD,
            COALESCE(MAX(DATE(t2.DATE, '+2 day')), '{start_dt}') as FETCH_START_DT,
            '{end_dt}' as FETCH_END_DT
        FROM
            FX_CD t1
        LEFT JOIN
            FX t2 ON t1.CURRENCY_CD = t2.CURRENCY_CD
        WHERE
            t1.CURRENCY_CD <> '#NA'
        GROUP BY
            t2.CURRENCY_CD
        '''

        df_missing = self.db_conn.read_query(query)

        print(df_missing)
        for _, row in df_missing.iterrows():
            ticker = yf.Ticker(row['CURRENCY_CD'])
            try:
                curr_hist = ticker.history(start=row['FETCH_START_DT'], end=row['FETCH_END_DT']).reset_index()
            except:
                print(row)
            curr_hist.columns = list(map(lambda x: x.upper(), curr_hist.columns))	

            curr_hist = curr_hist[['CLOSE', 'DATE']]
            curr_hist.rename(columns={
                'CLOSE' : 'VALUE'
            }, inplace=True)
            curr_hist['CURRENCY_CD'] = row['CURRENCY_CD']
            try:
                self.db_conn.insert_data(curr_hist, 'FX')
            except:
                print('Failed to insert: ', curr_hist, ' in FX')
    
    def fetch_missing_securities_yf(self, start_dt, end_dt):
        query = f'''
            SELECT
            t1.TICKER,
            COALESCE(DATE(DATETIME(MAX(DATE(t2.DATE)), '+1 day')), '{start_dt}') as FETCH_START_DT,
            '{end_dt}' as FETCH_END_DT
        FROM
            SECURITY t1
        LEFT JOIN
            SECURITY_VALUES t2 ON t1.TICKER = t2.TICKER
        WHERE
            t1.SRC = 'YF'
        GROUP BY
            t1.TICKER
        '''

        
        df_missing = self.db_conn.read_query(query)

        hists = []
        for _, row in df_missing.iterrows():
            try:
                ticker = yf.Ticker(row['TICKER'])
                hist = ticker.history(start=row['FETCH_START_DT'], end=row['FETCH_END_DT']).reset_index()
                hist['TICKER'] = row['TICKER']

                ref_date = utils.str2date(row['FETCH_START_DT'])
                hist = hist[hist.Date >= ref_date]


                hists.append(hist)
            except Exception as e:
                print(e)
                print(f'Ticker {row["TICKER"]} not found on yahoo finance')

        hist = pd.concat(hists, axis=0)
        hist = hist[['TICKER', 'Date', 'Open', 'High', 'Low', 'Close']]
        hist.columns = list(map(lambda x: x.upper(), hist.columns))	

        try:
            self.db_conn.insert_data(hist, 'SECURITY_VALUES')
        except Exception as e:
            print(e)

        return hist

    def fetch_missing_securities_bvb(self, start_dt, end_dt):
        now_ = datetime.now()
        
        query = f'''
            SELECT
            t1.TICKER,
            COALESCE(MAX(DATE(t2.DATE)), '{start_dt}') as FETCH_START_DT,
            '{end_dt}' as FETCH_END_DT
        FROM
            SECURITY t1
        LEFT JOIN
            SECURITY_VALUES t2 ON t1.TICKER = t2.TICKER
        WHERE
            t1.SRC = 'BVB_API'
        GROUP BY
            t1.TICKER
        '''


        def get_last_price(ticker):
            url = f'https://bvb.ro/FinancialInstruments/Details/FinancialInstrumentsDetails.aspx?s={ticker}'
            req = requests.api.get(url)
            page = bs4.BeautifulSoup(req.content, "html.parser")
            job_elements = page.find_all("tr", class_="TD2")
            last_price = None

            for el_ in job_elements:
                if "last" in el_.text.lower():
                    elements =  el_.findAll("td")
                    last_price = elements[-1].text
                    break
      
            return last_price
        


        bvb_tickers = self.db_conn.read_query(query)

        now_ = datetime.now().strftime(r'%Y-%m-%d')

        def isValid(dt1, dt2):
            return datetime.strptime(dt1, r'%Y-%m-%d') > datetime.strptime(dt2, r'%Y-%m-%d')

        bvb_tickers['filter'] = bvb_tickers.apply(lambda x: isValid(now_, x['FETCH_START_DT']), axis=1)

        bvb_tickers = bvb_tickers[bvb_tickers['filter'] == True]

        bvb_tickers['CLOSE'] = bvb_tickers['TICKER'].apply(get_last_price)
        bvb_tickers['DATE'] = now_

        bvb_tickers['OPEN'] = bvb_tickers['CLOSE'].values
        bvb_tickers['HIGH'] = bvb_tickers['CLOSE'].values
        bvb_tickers['LOW'] = bvb_tickers['CLOSE'].values

        bvb_tickers = bvb_tickers.drop(columns=['filter', 'FETCH_START_DT', 'FETCH_END_DT'])

        if len(bvb_tickers) == 0:
            return None
        
        table_handler = TableHandler(self.db_conn, 'SECURITY_VALUES', '')
        table_handler.insert_val(bvb_tickers.to_dict(orient='list'))

        return bvb_tickers