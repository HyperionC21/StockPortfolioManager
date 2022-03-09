import requests
import bs4
from flask import Flask
from flask import request

app = Flask(__name__)


@app.route('/')
def hello_world():
   return 'Hello World'

@app.route('/get_stock',methods = ['GET'])
def get_stock():
   ticker = request.args.get('ticker', None)
    
   def get_last_price(ticker):
      url = f'https://bvb.ro/FinancialInstruments/Details/FinancialInstrumentsDetails.aspx?s={ticker}'
      req = requests.api.get(url)
      page = bs4.BeautifulSoup(req.content, "html.parser")
      job_elements = page.find_all("tr", class_="TD2")
      last_price = None

      for el_ in job_elements:
         if "last" in el_.text.lower():
            elements =  el_.findAll("td")
            last_price = elements[-1].text
            break
      
      return last_price

   last_price = get_last_price(ticker)
   
   return last_price


if __name__ == '__main__':
   app.run()