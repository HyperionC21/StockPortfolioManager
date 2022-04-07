# backend
from ctypes import util
from distutils.log import debug
from tracemalloc import start
from turtle import width
import pandas as pd
import numpy as np
import json

from backend import base, reporting
from utils import utils
from datetime import datetime
import flask


# frontend
from dash import Dash, html, dcc, Input, Output, callback
from dash import dash_table
import dash
import plotly.express as px
app = Dash(__name__)

def get_evolution(start_dt, end_dt):
    db_connector = base.BaseDBConnector('core.db')
    db_fetcher = base.DataFetcher(db_connector)
    reporter = reporting.Reporter(db_fetcher)

    ref_nav = reporter.get_portfolio_info(1, start_dt)['nav']


    df_evolution = pd.DataFrame()
    df_evolution['DT'] = list(utils.daterange(start_dt, end_dt))
    df_evolution['NAV'] = df_evolution['DT'].apply(lambda x: reporter.get_portfolio_info(1, x)['nav'])
    df_evolution['RETURN'] = (df_evolution['NAV'] - ref_nav) * 100 / ref_nav

    return df_evolution

def get_composition(ref_date):
    db_connector = base.BaseDBConnector('core.db')
    db_fetcher = base.DataFetcher(db_connector)
    reporter = reporting.Reporter(db_fetcher)

    ref_cost = reporter.get_portfolio_info(1, ref_date)['cost']

    df_composition = reporter.get_portfolio_info(1, ref_date, ref_cost=ref_cost)['df']
    df_composition['PROFIT'] = np.round(df_composition['VALUE'] - df_composition['TOTAL_COST'], 2)
    df_composition['PROFIT%'] = np.round(df_composition['PROFIT'] * 100 / df_composition['TOTAL_COST'], 2)
    df_composition['VALUE%'] = np.round(df_composition['VALUE'] * 100 / df_composition['VALUE'].sum(), 2)

    df_composition['FX'] = np.round(df_composition['FX'], 2)

    df_composition['TOTAL_COST'] = df_composition['TOTAL_COST'].astype(int)
    df_composition['PRICE'] = df_composition['PRICE'].apply(lambda x: np.round(x, 2))
    
    df_composition.loc[df_composition['VALUE%'] <= 1, 'TICKER'] = 'OTHER'

    df_composition = df_composition.sort_values(by='VALUE', ascending=False)
    return df_composition

def get_form(fields, id_):
    def get_field(name):
        return html.Div([
                    html.Label(name),
                    dcc.Input(name=name),
                ],
                style={'display': 'flex', 'flex-direction': 'row', 'width' : '1000'}
            )

    fields = list(map(lambda x: get_field(x), fields))

    form_security = html.Form([
        *fields,
        html.Button('Submit', type='submit')
    ], action=f'/post_{id_}', method='post', id=id_)

    return form_security

def get_table(t_name):
    db_connector = base.BaseDBConnector('core.db')

    df = db_connector.read_table(t_name)

    if 'DATE' in df.columns:
        df = df.sort_values(by='DATE', ascending=False)
    

    table = dash_table.DataTable(df.to_dict('records'), 
        [{"name": i, "id": i} for i in df.columns],
        page_size=10,
        filter_action="native",
        sort_action="native",
        sort_mode="multi",
        style_table={
        'overflowY': 'scroll'
        }
    )

    return table

def update_data():
    db_connector = base.BaseDBConnector('core.db')
    missing_data_getter = base.DBUpdater(db_conn=db_connector)
    _ = missing_data_getter.fetch_missing_fx(START_DT, now_)
    _ = missing_data_getter.fetch_missing_securities_yf(START_DT, now_)
    _ = missing_data_getter.fetch_missing_securities_bvb(START_DT, now_)


INPUT_FORM_FIELDS = {
    'security' : ['TICKER', 'SECTOR', 'COUNTRY', 'FX', 'MARKET', 'SRC'],
    'transaction' : ['TICKER', 'PRICE', 'FX', 'AMOUNT', 'DATE'],
    'security_values' : ['TICKER', 'DATE', 'CLOSE']
}

gl_form_name = 'security'
START_DT = '2022-01-10'
now_ = utils.date2str(datetime.now())

def get_visual_data(start_dt, end_dt):
    df_ev = get_evolution(start_dt, end_dt)
    df_comp = get_composition(end_dt)

    fig_roi = px.line(df_ev, x='DT', y=['RETURN'])
    fig_value_pie = px.pie(df_comp, names='TICKER', values='VALUE', title='Portfolio value')
    fig_cost_pie = px.pie(df_comp, names='TICKER', values='TOTAL_COST', title='Portfolio invested')

    df_comp = df_comp[df_comp['TICKER'] != 'OTHER']
    fig_profit_perc = px.bar(df_comp.sort_values(by='PROFIT%', ascending=False), \
        x='TICKER', y='PROFIT%', color='TICKER', title='Percentage profit')
    fig_profit = px.bar(df_comp.sort_values(by='PROFIT', ascending=False), \
        x='TICKER', y='PROFIT', color='TICKER', title='Absolute profit')

    return {
        'ev' : df_ev,
        'comp' : df_comp,
        'fig_roi' : fig_roi,
        'fig_v_pie' : fig_value_pie,
        'fig_c_pie' : fig_cost_pie,
        'fig_pr_perc' : fig_profit_perc,
        'fig_pr' : fig_profit
    }

vis_data = get_visual_data(START_DT, now_)

if __name__ == '__main__':
    update_data()

    roi_div = html.Div(
        id='page-1-content',
        children=[
            html.Div([
                dcc.Graph(figure=vis_data['fig_roi'], id='roi_graph_id'),
                dcc.Tabs([
                    dcc.Tab(label='Interval Picker', children=[dcc.DatePickerRange(
                    id='roi_range',
                    min_date_allowed=utils.str2date(START_DT),
                    max_date_allowed=utils.str2date(now_)
                    )]),
                    dcc.Tab(label='Preset Picker', children=[dcc.Dropdown(['ALLTIME', 'WTD', 'MTD', 'YTD'], 'ALLTIME', id='period_dropdown_id')])
                ])
                ],
                style={'display': 'flex', 'flex-direction': 'column'}),
            dcc.Tabs([
                dcc.Tab(label='Value Portfolio Composition', children=[dcc.Graph(figure=vis_data['fig_v_pie'], id='v_pie_id')]),
                dcc.Tab(label='Invested Portfolio Composition', children=[dcc.Graph(figure=vis_data['fig_c_pie'], id='c_pie_id')])
            ]),
            html.Br(),
            dcc.Tabs([
               dcc.Tab(label='PROFIT', children=[html.H1(int(vis_data['comp']['PROFIT'].sum()))]),
               dcc.Tab(label='VALUE', children=[html.H1(int(vis_data['comp']['VALUE'].sum()))]),
               dcc.Tab(label='INV', children=[html.H1(int(vis_data['comp']['TOTAL_COST'].sum()))]) 
            ]),
            html.Br(),
            dcc.Tabs([
                dcc.Tab(label="Profit Percentage", children=[dcc.Graph(figure=vis_data['fig_pr_perc'])]),
                dcc.Tab(label="Profit Absolute", children=[dcc.Graph(figure=vis_data['fig_pr'])])
            ])
        ],
        style={'display': 'flex', 'flex-direction': 'column', 'width' : '1000'}
    )

    index_page = html.Div([
        dcc.Link(html.Button("STATISTICS"), href='/statistics'),
        html.Br(),
        dcc.Link(html.Button("SECURITY FORM"), href='/security_id'),
        html.Br(),
        dcc.Link(html.Button("TRANSACTION FORM"), href='/transaction_id'),
        html.Br(),
        dcc.Link(html.Button("SECURITY VALUES FORM"), href='/security_values_id'),
    ], style={"width": "500px",
        "margin": "auto",
        "border": "3px", 
        "solid" :  "#73AD21",
        "top" : 0,
        "bottom" : 0,
        "left" : 0,
        "right" : 0,
        "font-family" : "Times New Roman",
        "font-weight" : "bold",
        "font-size" : "40px"})

    page_1_layout = html.Div([
        roi_div,
        dcc.Link(html.Button("HOME"), href='/'),
    ])


    security_form = html.Div([
            get_form(INPUT_FORM_FIELDS['security'], 'security_id'),
            get_table('SECURITY'),
            dcc.Link(html.Button("HOME"), href='/')
    ])

    transaction_form = html.Div([
        get_form(INPUT_FORM_FIELDS['transaction'], 'transaction_id'),
        get_table('TRANSACTION'),
        dcc.Link(html.Button("HOME"), href='/')
    ])

    security_values_form = html.Div([
        get_form(INPUT_FORM_FIELDS['security_values'], 'security_values_id'),
        get_table('SECURITY_VALUES'),
        dcc.Link(html.Button("HOME"), href='/')
    ])

    @callback(Output('page-content', 'children'),
              [Input('url', 'pathname')])
    def display_page(pathname):
        if pathname == '/statistics':
            return page_1_layout
        elif pathname == '/security_id':
            return security_form
        elif pathname == '/transaction_id':
            return transaction_form
        elif pathname == '/security_values_id':
            return security_values_form
        else:
            return index_page
    
    @app.server.route('/post_security_id', methods=['POST'])
    def on_security_post():

        db_connector = base.BaseDBConnector('core.db')
        security_t_handler = base.TableHandler(db_connector, 'SECURITY', '')

        data = dict(flask.request.form)

        for k in data.keys():
            data[k] = [data[k]]

        security_t_handler.insert_val(data)
        return flask.redirect('/')

    @app.server.route('/post_transaction_id', methods=['POST'])
    def on_transaction_post():

        db_connector = base.BaseDBConnector('core.db')
        transaction_t_handler = base.TableHandler(db_connector, 'TRANSACTION', '')
        data = dict(flask.request.form)

        for k in data.keys():
            data[k] = [data[k]]
        
        transaction_t_handler.insert_val(data)
        return flask.redirect('/')

    @app.server.route('/post_security_values_id', methods=['POST'])
    def on_security_values_post():
        
        db_connector = base.BaseDBConnector('core.db')
        security_values_t_handler = base.TableHandler(db_connector, 'SECURITY_VALUES', '')
        
        data = dict(flask.request.form)
        
        for k in data.keys():
            data[k] = [data[k]]

        security_values_t_handler.insert_val(data)
        return flask.redirect('/')

    @app.callback(
        Output('roi_graph_id', 'figure'),
        Input('roi_range', 'start_date'),
        Input('roi_range', 'end_date'),
        Input('period_dropdown_id', 'value'))
    def update_output(start_date, end_date, value):
        ctx = dash.callback_context
        if ctx.triggered[0]['prop_id'] == 'period_dropdown_id.value':
            end_dt = utils.str2date(now_)
            
            from datetime import timedelta

            start_dt = utils.str2date(START_DT)
            
            if value == 'MTD':
                start_dt = end_dt.replace(day=1)
            elif value == 'WTD':
                start_dt = end_dt - timedelta(days=end_dt.weekday())
            elif value == 'YTD':
                start_dt = end_dt.replace(month=1, day=1) 
            
            if start_dt < utils.str2date(START_DT):
                start_dt = utils.str2date(START_DT)

            start_dt = utils.date2str(start_dt)
            end_dt = utils.date2str(end_dt)

            return get_visual_data(start_dt, end_dt)['fig_roi']
        else:
            return get_visual_data(start_date, end_date)['fig_roi']

    @app.callback(
        Output('v_pie_id', 'figure'),
        Input('roi_range', 'start_date'),
        Input('roi_range', 'end_date'))
    def update_v_pie(start_date, end_date):
        return get_visual_data(start_date, end_date)['fig_v_pie']
    

    @app.callback(
        Output('c_pie_id', 'figure'),
        Input('roi_range', 'start_date'),
        Input('roi_range', 'end_date'))
    def update_v_pie(start_date, end_date):
        return get_visual_data(start_date, end_date)['fig_c_pie']

    def serve_layout():
        return html.Div([
            dcc.Location(id='url', refresh=False),
            html.Div(id='page-content')
        ])

    app.layout = serve_layout()

    def serve_layout():
        return html.Div([
            dcc.Location(id='url', refresh=False),
            html.Div(id='page-content')
        ])

    app.layout = serve_layout()

    app.run_server(debug=True)