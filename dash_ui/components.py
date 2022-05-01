from backend import base
from utils import utils

from dash import Dash, html, dcc, Input, Output, callback
from dash import dash_table
import dash

INPUT_FORM_FIELDS = {
    'security' : ['TICKER', 'SECTOR', 'COUNTRY', 'FX', 'MARKET', 'SRC'],
    'transaction' : ['TICKER', 'PRICE', 'FX', 'AMOUNT', 'DATE'],
    'security_values' : ['TICKER', 'DATE', 'CLOSE']
}

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

def get_table(tb, db_path):
    if type(tb) == str:
        db_connector = base.BaseDBConnector(db_path)

        df = db_connector.read_table(tb)
    else:
        df = tb
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

def get_security_form(db_path):
    return html.Div([
        get_form(INPUT_FORM_FIELDS['security'], 'security_id'),
        get_table('SECURITY', db_path),
        dcc.Link(html.Button("HOME"), href='/')
])

def get_transaction_form(db_path):
    return html.Div([
        get_form(INPUT_FORM_FIELDS['transaction'], 'transaction_id'),
        get_table('TRANSACTION', db_path),
        dcc.Link(html.Button("HOME"), href='/')
    ])

def get_security_values_form(db_path):
    return html.Div([
    get_form(INPUT_FORM_FIELDS['security_values'], 'security_values_id'),
    get_table('SECURITY_VALUES', db_path),
    dcc.Link(html.Button("HOME"), href='/')
    ])

def get_statistics_page(vis_data, start_dt, end_dt, db_path):
    roi_div = html.Div(
        id='page-1-content',
        children=[
            html.Div([
                dcc.Tabs([
                    dcc.Tab(label='ROI', children=[dcc.Graph(figure=vis_data['fig_roi'], id='roi_graph_id')]),
                    dcc.Tab(label='NAV', children=[dcc.Graph(figure=vis_data['fig_nav'], id='nav_graph_id')]),
                    dcc.Tab(label='PROFIT', children=[dcc.Graph(figure=vis_data['graph_profit'], id='profit_graph_id')])
                ]),
                dcc.Tabs([
                    dcc.Tab(label='Interval Picker', children=[dcc.DatePickerRange(
                    id='roi_range',
                    min_date_allowed=utils.str2date(start_dt),
                    max_date_allowed=utils.str2date(end_dt)
                    )]),
                    dcc.Tab(label='Preset Picker', children=[dcc.Dropdown(['ALLTIME', 'WTD', 'MTD', 'YTD'], 'ALLTIME', id='period_dropdown_id')])
                ])
                ],
                style={'display': 'flex', 'flex-direction': 'column'}),
            dcc.Tab(label='Value Portfolio Composition', children=[dcc.Graph(figure=vis_data['fig_v_pie'], id='v_pie_id')]),
            html.Br(),
            dcc.Tabs([
                dcc.Tab(label="Profit Percentage", children=[dcc.Graph(figure=vis_data['fig_pr_perc'])]),
                dcc.Tab(label="Profit Absolute", children=[dcc.Graph(figure=vis_data['fig_pr'])])
            ]),
            html.Br(),
            get_table(vis_data['comp'], db_path=db_path)
        ],
        style={'display': 'flex', 'flex-direction': 'column', 'width' : '1000'}
    )

    return html.Div([
        roi_div,
        dcc.Link(html.Button("HOME"), href='/'),
    ])


def get_index_page():
    return html.Div([
        dcc.Link(html.Button("STATISTICS"), href='/statistics'),
        html.Br(),
        dcc.Link(html.Button("SECURITY FORM"), href='/security_id'),
        html.Br(),
        dcc.Link(html.Button("TRANSACTION FORM"), href='/transaction_id'),
        html.Br(),
        dcc.Link(html.Button("SECURITY VALUES FORM"), href='/security_values_id'),
    ])

def get_default_page():
    return html.Div([
            dcc.Location(id='url', refresh=False),
            html.Div(id='page-content')
    ])