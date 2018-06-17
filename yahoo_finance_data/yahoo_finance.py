#!/usr/bin/env python

import re
import time
import datetime
import requests
import functools

import warnings


COVERAGE_TRESHOLD = 0.9

WEEKLY = "1wk"
DAILY = "1d"
MONTHLY = "1mo"

COOKIE_CACHE, CRUMB2_CACHE = None, None
USE_CACHE = True


def find_crumb_store(lines):
    # Looking for
    # ,"CrumbStore":{"crumb":"9q.A4D1c.b9
    for l in lines:
        if re.findall(r'CrumbStore', l):
            return l
    print "Did not find CrumbStore"


def get_page_data(symbol):
    url = "https://finance.yahoo.com/quote/%s/?p=%s" % (symbol, symbol)
    r = requests.get(url)
    cookie = {'B': r.cookies['B']}
    # lines = r.text.encode('utf-8').strip().replace('}', '\n')
    lines = r.content.strip().replace('}', '\n')
    return cookie, lines.split('\n')


def get_cookie_crumb(symbol):
    global COOKIE_CACHE, CRUMB2_CACHE

    if not COOKIE_CACHE or not CRUMB2_CACHE or not USE_CACHE:
        cookie, lines = get_page_data(symbol)
        crumb = find_crumb_store(lines).split(':')[2].strip('"')
        # Note: possible \u002F value
        # ,"CrumbStore":{"crumb":"FWP\u002F5EFll3U"
        # FWP\u002F5EFll3U
        crumb2 = crumb.decode('unicode-escape')
    
    return cookie, crumb2


def get_data(symbol, start_date, end_date, cookie, crumb, event="history", interval="1d"):
    # events: history, div, split
    url = "https://query1.finance.yahoo.com/v7/finance/download/%s?period1=%s&period2=%s&interval=%s&events=%s&crumb=%s" % (
        symbol, start_date, end_date, interval, event, crumb)
    response = requests.get(url, cookies=cookie)
    return response.text


def get_now_epoch():
    # @see https://www.linuxquestions.org/questions/programming-9/python-datetime-to-epoch-4175520007/#post5244109
    return int(time.mktime(datetime.datetime.now().timetuple()))


def yield_raw_csv(csv, target_type=float):
    def transform(i):
        try:
            return target_type(i)
        except ValueError:
            return None

    lines = csv.splitlines()
    labels = lines[0].split(",")

    for line in lines[1:]:
        values = line.split(",")
        values[0] = datetime.datetime.strptime(values[0], "%Y-%m-%d")
        values[1:] = map(transform, values[1:])
        
        yield dict(zip(labels, values))


def download(symbol, start_date=None, end_date=None, event="history", interval="1d"):
    start_date = 0 if start_date is None else int(time.mktime(start_date.timetuple()))
    end_date = end_date or get_now_epoch()

    assert start_date >= 0
    assert start_date <= end_date

    cookie, crumb = get_cookie_crumb(symbol)
    raw_csv = get_data(symbol, start_date, end_date, cookie, crumb, event, interval)

    return list(yield_raw_csv(raw_csv, str if event == "split" else float))


def synchronize_price_data(data_generator):

    date_series = [[day["Date"] for day in stock_data if day["Close"]] for stock_data in data_generator]
    all_dates = set(reduce(lambda a, b: a + b, date_series))

    common_dates = set(date_series[0])
    for date_serie in date_series[1:]:
        common_dates = common_dates.intersection(date_serie)
    
    sync_data = [[day for day in stock_data if day["Date"] in common_dates] for stock_data in data_generator]

    coverage = (len(common_dates) / float(len(all_dates)))

    if coverage <= COVERAGE_TRESHOLD:
        warnings.warn("Coverage treshold hit: resulting coverage is %.2f%% (%.2f%% data loss)." \
            % (coverage, 1 - coverage))

    return sync_data


def get_synchronized_returns(sync_data):
    return_vector = []

    for stock_data in sync_data:
        stock_rets = []

        for day_nr, day in enumerate(stock_data[:-1]):
            stock_rets.append(stock_data[day_nr + 1]["Close"] / day["Close"] - 1.0)

        return_vector.append(stock_rets)

    return return_vector


download_quotes = functools.partial(download, event="history")
download_dividends = functools.partial(download, event="div")
download_splits = functools.partial(download, event="split")


if __name__ == "__main__":
    universe = ["SAP.DE", "SAP.DE", "BAS.DE"]
    data = [download_quotes(symbol, interval="1d") for symbol in universe]
    syncd = synchronize_price_data(data)
    RV = get_synchronized_returns(syncd)
    print RV[0][:10]