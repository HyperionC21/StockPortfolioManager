from datetime import datetime, timedelta

def date2str(dt : datetime):
    return dt.strftime(r'%Y-%m-%d')

def str2date(dt : str):
    return datetime.strptime(dt, r'%Y-%m-%d')

def daterange(start_date : str, end_date : str):
    start_dt = str2date(start_date)
    end_dt = str2date(end_date)

    for n in range(int((end_dt - start_dt).days)):
        yield start_dt + timedelta(n)