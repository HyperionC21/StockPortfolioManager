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
    
    def fetch_missing_hist(self, ref_date):
        
        query_fst_trans_per_ticker = '''
            SELECT
                t1.TICKER,
                MIN(DATE(t1.DATE)) as "FST_BUY_DT"
            FROM
                'TRANSACTION' t1
            GROUP BY
                t1.TICKER
        '''

        fst_dt = self.db_conn.read_query(query_fst_trans_per_ticker)

        query_lst_data_per_ticker = '''
            SELECT
                t1.TICKER,
                MAX(DATE(t1.DATE)) as "MAX_STORED_DT"
            FROM
                'SECURITY_VALUES' t1
            GROUP BY
                t1.TICKER
        '''

        lst_dt = self.db_conn.read_query(query_lst_data_per_ticker)

        df_ticker_fetch = pd.merge(fst_dt, lst_dt, on='TICKER', how='left')
 
        df_ticker_fetch = df_ticker_fetch.fillna('3000-01-01')

        def get_min_date(dt1, dt2):
            dt1 = datetime.strptime(dt1, r'%Y-%m-%d')
            dt2 = datetime.strptime(dt2, r'%Y-%m-%d')

            return min(dt1, dt2)

        df_ticker_fetch['START_DT'] = df_ticker_fetch.apply(lambda x: get_min_date(x['FST_BUY_DT'], x['MAX_STORED_DT']), axis=1)
        df_ticker_fetch['END_DT'] = ref_date

        df_ticker_fetch['START_DT'] = df_ticker_fetch['START_DT'].apply(lambda x: x.strftime(r'%Y-%m-%d'))

        hists = []
        for _, row in df_ticker_fetch.iterrows():
            try:
                ticker = yf.Ticker(row['TICKER'])
                hist = ticker.history(start=row['START_DT'], end=row['END_DT']).reset_index()
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
