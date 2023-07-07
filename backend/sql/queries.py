
# RETRIEVES THE PORTOFLIO STARTING TRADE DATE
FST_TICKER_TRANS_QUERY = '''
            SELECT
                MIN(DATE(t1.DATE)) as "FST_BUY_DT"
            FROM
                'TRANSACTION' t1
        '''

PORTFOLIO_COMP_QUERY = '''
            SELECT
                t1.TICKER,
                t2.SECTOR,
                t2.COUNTRY,
                t2.FX,
                SUM(t1.FEE * t1.FX) as TOTAL_FEE,
                SUM(t1.AMOUNT) as N_SHARES,
                SUM(t1.AMOUNT * t1.PRICE * t1.FX) as TOTAL_COST,
                '{}' as DT
            FROM
                'TRANSACTION' as t1
            INNER JOIN
                'SECURITY' as t2
            ON
                t1.TICKER = t2.TICKER
            WHERE
                1 = 1
                AND DATE(t1.DATE) <= DATE('{}')
            GROUP BY
                t1.TICKER
            HAVING SUM(t1.AMOUNT) > 0 
        '''

CURRENCY_QUERY = '''
            SELECT
                FX,
                CURRENCY_CD 
            FROM
                `FX_CD`
            WHERE
                1 = 1
                AND FX <> '#NA'
        '''

FX_VAL_QUERY = '''
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
                    AND DATE(t1.DATE) <= DATE('{}')
            )
            WHERE
                1 = 1
                AND RNK = 1
            '''

DIVIDEND_AMT_QUERY = '''
    SELECT
        SUM(AMOUNT * FX)  "AMT"
    FROM
        `DIVIDEND` t1
    WHERE
        1 = 1
        AND DATE(t1.DATE) >= DATE('{}') AND DATE(t1.DATE) <= DATE('{}')
'''

FX_MISSING_INTERVALS = '''
        SELECT
            t1.CURRENCY_CD,
            COALESCE(MAX(DATE(t2.DATE, '+1 day')), '{}') as FETCH_START_DT,
            '{}' as FETCH_END_DT
        FROM
            FX_CD t1
        LEFT JOIN
            FX t2 ON t1.CURRENCY_CD = t2.CURRENCY_CD
        WHERE
            t1.CURRENCY_CD <> '#NA'
        GROUP BY
            t2.CURRENCY_CD
        '''

ALL_TICKERS_QUERY = '''
            SELECT DISTINCT 
                t1.TICKER
            FROM `SECURITY` t1
            WHERE
                1 = 1
                AND t1.SRC <> 'MANUAL'
        '''

TICKER_PRICES_QUERY = '''
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
                    DATE(DATE) <= DATE('{}')
                GROUP BY
                    TICKER
            ) t2
            ON t1.TICKER = t2.TICKER AND DATE(t1.DATE) = DATE(t2.DATE)
            WHERE
                1 = 1
                AND t1.TICKER IN ({}) '''

TICKERS_FX_QUERY = '''
            SELECT
            t1.TICKER,
            t2.CURRENCY_CD
        FROM
            SECURITY t1
        LEFT JOIN
            FX_CD t2 ON t1.FX = t2.FX
        WHERE
            1 = 1
            AND t1.TICKER IN ({})
        '''

FST_TRANS_TICKER_QUERY = '''
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

MISSING_TICKERS_DATA_QUERY = '''
            SELECT
            t1.TICKER,
            t1.SRC,
            COALESCE(DATE(DATETIME(MAX(DATE(t2.DATE)), '+1 day')), '{}') as FETCH_START_DT,
            '{}' as FETCH_END_DT
        FROM
            SECURITY t1
        LEFT JOIN
            SECURITY_VALUES t2 ON t1.TICKER = t2.TICKER
        WHERE
            t1.SRC IN ('YF', 'BVB')
        GROUP BY
            t1.TICKER
        '''

LAST_TRANS_TICKER = '''
    SELECT 
        TICKER,
        DATE,
        AMOUNT as N_SHARES
    FROM `TRANSACTION`
    WHERE TICKER = '{}'
    ORDER BY DATE DESC
    LIMIT {}
'''

LAST_DIVIDEND_TICKER = '''
    SELECT 
        TICKER,
        DATE,
        AMOUNT as AMT
    FROM `DIVIDEND`
    WHERE TICKER = '{}'
    ORDER BY DATE DESC
    LIMIT {}
'''

SECURITY_DIV_VAL = '''
    SELECT
        SUM(AMOUNT * FX)
    FROM
        `DIVIDEND`
    WHERE TICKER = '{}'
'''