from dash import Dash, html, dcc, Input, Output
import plotly.express as px
import pandas as pd

from backend import fx_fetcher, misc_fetcher, ticker_fetcher, base, api
from utils import utils
from datetime import datetime, date

import requests

app = Dash(__name__)

BACKEND_URL = "http://127.0.0.1:5000"

# UI CONFIG
PERFORMANCE_STEP = 2

app.layout = html.Div(children=[
    html.H1(children='Portfolio Manager'),
    html.Div(
        children=[
            html.H2(children="Portfolio Performance"),
            dcc.Tabs(
                children = [
                    dcc.Tab(label="AGG Performance", children = html.Div(children=[
                        dcc.Graph(id='portfolio_performance_fig_id'),
                        dcc.DatePickerRange(
                            id='performance_picker_id',
                            min_date_allowed=date(2022, 1, 10),
                            max_date_allowed=datetime.now().date(),
                            initial_visible_month=date(2022, 1, 10),
                            end_date=datetime.now().date()
                        ),
                        dcc.Dropdown(options=['Absolute', 'Percentage'], id='kind_picker_id')
                        ])),
                    dcc.Tab(label="Split Performance", children = html.Div(children=[
                        dcc.Graph(id='portfolio_performance_split_fig_id'),
                        dcc.DatePickerRange(
                            id='performance_picker_split_id',
                            min_date_allowed=date(2022, 1, 10),
                            max_date_allowed=datetime.now().date(),
                            initial_visible_month=date(2022, 1, 10),
                            end_date=datetime.now().date()
                        )
                        ])),
                ]
            ),
            
        ]
    ),
    html.Div(
        children=[
            html.H2(children="Porfolio Distribution"),
            dcc.DatePickerSingle(
                id='portfolio_distrib_date_picker_id',
                min_date_allowed=date(2022, 1, 10),
                max_date_allowed=datetime.now().date(),
                initial_visible_month=date(2022, 1, 10),
                date=datetime.now().date()
            ),
            dcc.Graph(id='Pie_Chart_Portfolio_id')
        ]
    ),
])

@app.callback(
    Output("Pie_Chart_Portfolio_id", "figure"),
    Input("portfolio_distrib_date_picker_id", "date")
)
def update_portfolio(date):
    r = requests.get(f"{BACKEND_URL}/composition", 
        params={
            "ref_date" : date 
        }
    )

    df_tmp = pd.DataFrame(r.json())
    out_fig = px.pie(df_tmp, names='TICKER', values='TOTAL_VALUE')
    
    return out_fig

@app.callback(
    Output('portfolio_performance_fig_id', 'figure'),
    Input('performance_picker_id', 'start_date'),
    Input('performance_picker_id', 'end_date'),
    Input('kind_picker_id', 'value'))
def update_output(start_date, end_date, value):
    r = requests.get(f"{BACKEND_URL}/performance", 
        params={
            "start_date" : start_date, 
            "end_date" : end_date, 
            "step" : PERFORMANCE_STEP,
            "kind" :  value
        }
    )
    df_tmp = pd.DataFrame(r.json())

    
    df_tmp['date'] = df_tmp['date'].apply(lambda x: utils.str2date(x))

    fig_ = px.line(df_tmp, 'date', 'profit', markers=True)

    return fig_

@app.callback(
    Output('portfolio_performance_split_fig_id', 'figure'),
    Input('performance_picker_split_id', 'start_date'),
    Input('performance_picker_split_id', 'end_date'))
def update_performance_split(start_date, end_date):
    r = requests.get(f"{BACKEND_URL}/performance_split", 
        params={
            "start_date" : start_date, 
            "end_date" : end_date, 
            "step" : PERFORMANCE_STEP,
        }
    )
    df_tmp = pd.DataFrame(r.json())

    df_tmp['DATE'] = df_tmp['DATE'].apply(lambda x: utils.str2date(x))
    print(df_tmp.groupby("DATE").count())
    fig_ = px.line(df_tmp, 'DATE', 'PROFIT%', color="TICKER", markers=True)

    return fig_

if __name__ == '__main__':
    app.run_server(debug=True)

    