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
        self.db_path = db_path
    
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
    def __init__(self, db_conn: BaseDBConnector):
        self.db_conn = db_conn

    def fetch_query(self, query):
        return  self.db_conn.read_query(query)
