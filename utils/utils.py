from datetime import datetime, timedelta

def date2str(dt : datetime):
    return dt.strftime(r'%Y-%m-%d')

def str2date(dt : str):
    return datetime.strptime(dt, r'%Y-%m-%d')

def daterange(start_date : str, end_date : str, step : int=1):
    start_dt = str2date(start_date)
    end_dt = str2date(end_date)

    seen_end_dt = False
    
    for n in range(0, int((end_dt - start_dt).days), step):
        dt = start_dt + timedelta(n)
        if dt == end_date:
            seen_end_dt = True
        yield dt
    
    if not seen_end_dt:
        yield end_date
    