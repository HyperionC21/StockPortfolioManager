import requests
from flask import Flask
from flask import request, render_template

import backend
import json

app = Flask(__name__)

@app.route('/', methods = ['GET', 'POST'])
def home():
    if request.args is not None:
        form_args = dict(request.json)
        print(form_args)
    return render_template(r'security_form.html')

if __name__ == "__main__":
    app.run()