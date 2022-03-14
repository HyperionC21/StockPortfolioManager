import pandas as pd
class Reporter:
    def __init__(self, connector):
        self._db_connector = connector

    def get_portfolio_composition(self, portfolio_id : int, ref_date : str):
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

        df = self._db_connector.read_query(query)
        
        return df

    def get_portfolio_nav(self, portfolio_id, ref_date):
        portfolio_composition = self.get_portfolio_composition(portfolio_id, ref_date)

        tickers = list(map(lambda x: f"'{x}'", list(portfolio_composition['TICKER'])))

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
                AND t1.TICKER IN ({",".join(tickers)})
        '''
        
        prices = self._db_connector.read_query(query)

        df_out = pd.merge(portfolio_composition, prices, on='TICKER', how='inner')

        df_out['VALUE'] = df_out['N_SHARES'] * df_out['PRICE']

        nav = df_out['VALUE'].sum()

        return nav
