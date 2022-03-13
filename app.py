import requests
from flask import Flask
from flask import request, render_template

from backend import base
import pandas as pd
import json

app = Flask(__name__)


@app.route('/security', methods = ['GET', 'POST'])
def security_form_handler():

    values = request.args.to_dict(flat=True)
    for k in values.keys():
        values[k] = [values[k]]
    
    db_connector = base.BaseDBConnector('core.db')
    security_handler = base.TableHandler(db_connector, 'SECURITY', 'TICKER')

    try:
        security_handler.insert_val(values)
    except Exception as e:
        print(e)


    return render_template(r'security_form.html')


@app.route('/dividend', methods = ['GET', 'POST'])
def dividend_form_handler():

    values = request.args.to_dict(flat=True)
    for k in values.keys():
        values[k] = [values[k]]

    values['ID'] = None

    db_connector = base.BaseDBConnector('core.db')
    dividend_handler = base.TableHandler(db_connector, 'DIVIDEND', '')

    try:
        dividend_handler.insert_val(values)
    except Exception as e:
        print(e)


    return render_template(r'dividend_form.html')

@app.route('/transaction', methods = ['GET', 'POST'])
def transaction_form_handler():

    values = request.args.to_dict(flat=True)
    for k in values.keys():
        values[k] = [values[k]]
    
    values['ID'] = None

    db_connector = base.BaseDBConnector('core.db')
    transaction_handler = base.TableHandler(db_connector, 'TRANSACTION', 'ID')

    try:
        transaction_handler.insert_val(values)
    except Exception as e:
        print(e)


    return render_template(r'transaction_form.html')

if __name__ == "__main__":

    app.run(debug=True)