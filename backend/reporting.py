import base


class Reporter:
    def __init__(self, db_model, connector):
        self._db_connector = connector
        self._db_model = db_model

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


    

class PortfolioReporter(Reporter):
    def __init__(self, db_model : dict, conn : base.BaseDBConnector):
        super().__init__(db_model, conn)
    
