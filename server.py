from crypt import methods
from weakref import ref
from flask import Flask, request
from backend import base, reporting
# Flask constructor takes the name of 
# current module (__name__) as argument.
app = Flask(__name__)
  

def get_db_backend(db_path):
    connector = base.BaseDBConnector(db_path)
    fetcher = reporting.DataFetcher(connector)
    reporter = reporting.Reporter(fetcher)

    return {
        'connector' : connector,
        'fetcher' : fetcher,
        'reporter' : reporter
    }

# The route() function of the Flask class is a decorator, 
# which tells the application which URL should call 
# the associated function.
@app.route('/')
# ‘/’ URL is bound with hello_world() function.
def hello_world():
    return 'Hello World'

@app.route('/nav_cost', methods=['GET'])
def portfolio():
    print(request.content_type)
    
    req_json = request.json

    try:
        ref_date = req_json['dt']
        portfolio_id = req_json['id']

        db_backend = get_db_backend('core.db')

        return db_backend['reporter'].get_nav_cost(portfolio_id, ref_date)
    except:
        return None

# main driver function
if __name__ == '__main__':
    
    # run() method of Flask class runs the application 
    # on the local development server.
    app.run(debug=False)