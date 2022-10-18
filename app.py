from dash import Dash, html, dcc, Input, Output
import plotly.express as px
import pandas as pd

from backend import fx_fetcher, misc_fetcher, ticker_fetcher, base, api
from utils import utils
from datetime import datetime, date

db_conn = base.BaseDBConnector('core.db')
ticker_fetcher_ = ticker_fetcher.TickerFetcher(db_conn)
fx_fetcher_ = fx_fetcher.FxFetcher(db_conn)

import requests

ticker_fetcher_.fetch_ticker_hist('2022-01-01', utils.date2str(datetime.now()))
fx_fetcher_.fetch_missing_fx('2022-01-01', utils.date2str(datetime.now()))

app = Dash(__name__)

BACKEND_URL = "http://127.0.0.1:5000"

# UI CONFIG
PERFORMANCE_STEP = 7

app.layout = html.Div(children=[
    html.H1(children='Portfolio Manager'),
    html.Div(
        children=[
            dcc.Graph(id='portfolio_performance_fig_id'),
            dcc.DatePickerRange(
                id='performance_picker_id',
                min_date_allowed=date(2022, 1, 9),
                max_date_allowed=datetime.now().date(),
                initial_visible_month=date(2022, 1, 10),
                end_date=date(2022, 7, 1)
            )
        ]
    )
,

])

@app.callback(
    Output('portfolio_performance_fig_id', 'figure'),
    Input('performance_picker_id', 'start_date'),
    Input('performance_picker_id', 'end_date'))
def update_output(start_date, end_date):
    r = requests.get(f"{BACKEND_URL}/performance", 
        params={
            "start_date" : start_date, 
            "end_date" : end_date, 
            "step" : PERFORMANCE_STEP
        }
    )
    df_tmp = pd.DataFrame(r.json())
    df_tmp['date'] = df_tmp['date'].apply(lambda x: utils.str2date(x))
    fig_ = px.line(df_tmp, 'date', 'profit')

    print(df_tmp.head())
    return fig_

if __name__ == '__main__':
    app.run_server(debug=True)