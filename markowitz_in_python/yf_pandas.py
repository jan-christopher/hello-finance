#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
This script provides a low-level access to yahoo finance data. 

Copyright (c) 2018, Jan-Christopher Magel
License: MIT (see LICENSE for details)
"""
import functools

import numpy
import pandas

from yahoo_finance import *


__author__ = 'Jan-Christopher Magel'
__version__ = '0.12dev'
__license__ = 'MIT'


PRICE_DATA_KEY = "Adj Close"

# Backup of old download function
__download_list_format = download



# override old download function
def download(symbols, start_date=None, end_date=None, event="history", interval="1d"):
	''' x '''

	data = __download_list_format(symbols, start_date, end_date, event, interval)

	if event != "history":
		return data

	synced = synchronize(data)

	labels = [symbols] if type(symbols) == type("") else symbols

	return data2pandas(synced, labels)


def data2pandas(data, labels, key="Close"):
	''' x '''
	dates = [day["Date"] for day in data[0]]

	q = [[day[key] for day in stock] for stock in data]
	q = numpy.asarray(q)
	df = pandas.DataFrame(q.T, index=dates, columns=labels)
	return df


# Reconnect high level shortcuts
download_quotes = functools.partial(download, event="history")
download_dividends = functools.partial(download, event="div")
download_splits = functools.partial(download, event="split")



if __name__ == "__main__":
	print download_quotes("IBM GILD".split(" ")).head()
	print download_dividends("IBM")
	print download_splits("IBM")
