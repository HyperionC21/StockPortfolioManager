import pandas as pd
import sqlite3
import pandas as pd


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

class TableHandler:
    def __init__(self, db_connector, table_name, db_config) -> None:
        pass