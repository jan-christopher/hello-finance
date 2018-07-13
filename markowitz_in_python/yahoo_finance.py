#
# ToDo

# get_return_vector(symbolS)
# synchronize(symbolS)
# download*(symbolS)
#


#!/usr/bin/env python
from __future__ import division

import re
import time
import datetime
import requests
import warnings
import functools


# Define coverage treshold for 
# synchronize_price_data()
COVERAGE_TRESHOLD = 0.9

# Define time intervals
WEEKLY, DAILY, MONTHLY = "1wk", "1d", "1mo"

# Some other global vars
USE_GENERATOR = False
GEN = lambda obj: obj if USE_GENERATOR else list(obj)
USE_CACHE = True
CACHE = {
    "cookie" : None,
    "crumb" : None
}


# We start with some utility functions:


def _get_www_raw(symbol):
    ''' Downloads the cookies and the raw content of a yahoo finance page. '''

    url = "https://finance.yahoo.com/quote/%s/?p=%s" % (symbol, symbol)
    r = requests.get(url)
    return r.cookies, r.content.decode("unicode-escape")


def _to_unix_epoch(dt=None):
    ''' Converts a datetime object into a 1970 unix epoch number. '''

    # @see https://www.linuxquestions.org/questions/programming-9/
    # python-datetime-to-epoch-4175520007/#post5244109
    
    if dt is None:
        dt = datetime.datetime.now()

    return int(time.mktime(dt.timetuple()))


def _process_raw_csv(csv, target_type=float):
    ''' Converts a raw csv string into dict. Values are converted
        to target_type. If a value can't be converted None is 
        inserted.'''

    def transform(i):
        try:
            return target_type(i)
        except ValueError:
            return None

    lines = csv.splitlines()

    # the first line always contains the labels
    labels = lines[0].split(",")

    for line in lines[1:]:
        values = line.split(",")
        # the first column is always the date col
        # we transform the string into a datetime obj
        values[0] = datetime.datetime.strptime(values[0], "%Y-%m-%d")

        # the rest of the values are usually floats
        values[1:] = map(transform, values[1:])
        
        yield dict(zip(labels, values))


# Now we continue with the main functions:


def get_cookie_and_crumb(symbol):
    ''' Extracts the specific cookie and crumb value. '''

    if not all(CACHE.values()) or not USE_CACHE:

        cookies, raw = _get_www_raw(symbol)
        
        # we try to find the crumb value using re
        # we know that the crumb value is always 11
        # chars long. Usually it is [a-zA-Z] but
        # sometimes there are some confusing chars
        # (see below)
        try:
            pattern = r'"CrumbStore":{"crumb":"[\w\/\.]{11}"}'
            crumb = re.findall(pattern, raw)[0].split('"')[-2]
        except IndexError:
            raise RuntimeError, "Could not find crumb store. Please retry or consider updating the pattern."

        # knwon unusal crumb values
        # {"crumb":"hGjK6pd8E0\u002F"}
        # {"crumb":"FWP\u002F5EFll3U"}

        # we update the cache
        CACHE["cookie"] = dict(B=cookies["B"])
        CACHE["crumb"] = crumb

    return CACHE["cookie"], CACHE["crumb"]


def get_raw_csv_data(symbol, start_date, end_date, event="history", interval="1d"):
    ''' Low level function for downloading the desired csv data (raw!).
        I would rather recommend using the shortcut functions instead of 
        calling get_raw_csv_data() directly. 
    '''

    cookie, crumb = get_cookie_and_crumb(symbol)

    # known events: 
    # history => historic price data
    # div => historic dividend data
    # split => historic split data

    url = "https://query1.finance.yahoo.com/v7/finance/download/%s?period1=%s&period2=%s&interval=%s&events=%s&crumb=%s" % (
        symbol, start_date, end_date, interval, event, crumb)

    response = requests.get(url, cookies=cookie)
    return response.text


def download(symbols, start_date=None, end_date=None, event="history", interval="1d"):
    ''' Medium level function  for downloading and converting the csv data.'''

    if start_date is None:
        # If not starting date is defined
        # we start at the beginning of the unix time epoch
        # by definition this is 0
        start_date = 0
    else:
        # we transform the datetime.date object
        # into the unix time epoch
        start_date = _to_unix_epoch(start_date)

    # we also transform the end_date...
    end_date = _to_unix_epoch(end_date)

    # some backup checks...
    assert start_date >= 0
    assert start_date <= end_date

    # lets check if we have multiple symbols or just one.
    # if symbols is a string we simply make a list out of it
    if type(symbols) == type(""):
        symbols = [symbols]

    # get the raw csv
    raw_csv = [get_raw_csv_data(s, start_date, end_date, event, interval) for s in symbols]

    final_data = [GEN(_process_raw_csv(csv, str if event == "split" else float)) for csv in raw_csv]
    return final_data


def synchronize(data):
    ''' Synchronizes multiple price series of different assets in order to 
        align the dates. 
    '''

    # first we compute the trading_dates of each asset
    date_series = [[day["Date"] for day in stock_data if day["Close"]] for stock_data in data]

    # then we compute the union of all trading dates
    all_dates = set(reduce(lambda a, b: a + b, date_series))

    # we start filtering trading dates using set().intersection()
    common_dates = set(date_series[0])
    for date_serie in date_series[1:]:
        common_dates = common_dates.intersection(date_serie)
    
    # we put all trading days together which appear in common_days
    synced_data = [[day for day in stock_data if day["Date"] in common_dates] for stock_data in data]

    # we also compute the coverage rate in order to avoid misleading results
    coverage = len(common_dates) / len(all_dates)
    if coverage <= COVERAGE_TRESHOLD:
        warnings.warn("Coverage treshold hit: resulting coverage is %.2f%%." \
                      "Shortest data set: index %d." % (
            (coverage * 100),
            map(len, date_series).index(min(map(len, date_series)))
        ))

    return synced_data


def get_return_vector(symbols, sync=True, **kwargs):
    ''' Computes a return vector.  '''

    # download the data
    data = download_quotes(symbols, **kwargs)

    return_vector = []

    # we synchronize first in order to avoid shifted return
    # series and divisions by None
    if sync:
        data = synchronize(data)
    else:
        warnings.warn("'data' will not be synchronized!")

    for stock in data:
        returns = []

        for day_nr, day in enumerate(stock[:-1]):
            returns.append(stock[day_nr + 1]["Close"] / day["Close"] - 1.0)

        return_vector.append(returns)

    return return_vector


# Create high level shortcuts
download_quotes = functools.partial(download, event="history")
download_dividends = functools.partial(download, event="div")
download_splits = functools.partial(download, event="split")


if __name__ == "__main__":
    
    import numpy
    universe = ["ADS.DE", "SAP.DE", "BAS.DE"]
    data = [download_quotes(symbol, interval=WEEKLY) for symbol in universe]
    RV = get_return_vector(universe)
    print numpy.corrcoef(RV)
    print download_quotes("GILD", interval=WEEKLY)[-1]