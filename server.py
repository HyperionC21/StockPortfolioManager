from datetime import datetime
from flask import Flask, redirect, url_for, request


from backend import fx_fetcher, misc_fetcher, ticker_fetcher, base, api
from utils import utils

import pandas as pd

app = Flask(__name__)

DB_PATH = 'core.db'

@app.route("/")
def home():
    return "Hello, World!"

@app.route("/portfolio")
def portfolio():
    ref_date = request.args.get("ref_date", utils.date2str(datetime.now()))

    portfolio_stats_ = api.PortfolioStats('core.db', ref_date)
    return portfolio_stats_.df_portfolio.to_dict()

@app.route("/performance")
def performance():
    
    db_conn = base.BaseDBConnector(DB_PATH)
    misc_fetcher_ = misc_fetcher.MiscFetcher(db_conn)
    start_dt = request.args.get("start_date", misc_fetcher_.fetch_fst_trans())
    end_dt = request.args.get("end_date", utils.date2str(datetime.now()))
    step = int(request.args.get("step", 1))

    print(start_dt, end_dt, step)

    date_range = utils.daterange(start_dt, end_dt, step)

    df_profits = pd.DataFrame()
    df_profits['date'] = list(date_range)
    df_profits['profit'] = df_profits.date.apply(lambda x: api.PortfolioStats('core.db', x).get_profit())
    df_profits['date'] = df_profits['date'].apply(lambda x: utils.date2str(x))

    return df_profits.to_dict()



if __name__ == "__main__":
    app.run(debug=True)