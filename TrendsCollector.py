import argparse
import collections
from datetime import datetime
import time
from types import TracebackType
from typing import Any, Optional, Type
import pandas as pd
import urllib3
import yaml
from pytrends.request import TrendReq
import os
import logging
import redis

class PyTrendsWrapper:
    """
    A wrapper over pytrends that caches results into a file
    """

    def __init__(self, pytrends_kwargs: dict[str, Any], request_kwargs: dict[str, Any]):
        """
        ctor
        :param pytrends_kwargs: The keyword arguments to be passed to pytrends on init
        :param request_kwargs: The keyword arguments to be passed to pytrends on payload build
        """

        self.pytrends_kwargs = pytrends_kwargs.copy()
        self.request_kwargs = request_kwargs.copy()
        self.pytrends = TrendReq(**pytrends_kwargs)
        self.call_count = 0

        self.redis_cache = redis.Redis()
        self.key_prefix = "Request Arguments: [" + ", ".join(str(t) for t in sorted(self.request_kwargs.items())) + "] -- "

    def get(self, key: frozenset[str]) -> pd.DataFrame:
        """
        Gets the data from the cache or pytrends
        :param key: The set of arguments to lookup
        :return: A DataFrame with the resulting data
        """

        cache_key = self.key_prefix + "Keys: [" + ", ".join(sorted(key)) + "]"

        logging.debug(f"PyTrends Request: {key} with cache key: {cache_key}")

        if cache_key not in self.redis_cache:
            logging.debug(f"PyTrends Request Not in Cache and Required Web Call: {key} -- number of web calls {self.call_count}")
            self.pytrends.build_payload(key, **self.request_kwargs)
            df = self.pytrends.interest_over_time()

            self.redis_cache.set(cache_key, yaml.dump(df, encoding='utf-8'))
            self.call_count += 1

        return yaml.load(self.redis_cache.get(cache_key), Loader=yaml.Loader)

def optimized_sort(pytrends_wrapper: PyTrendsWrapper, input_list: list[str]):
    """
    Partially sorts input_list based on their max GoogleTrends data
    :param pytrends_wrapper: The pytrends wrapper
    :param input_list: The input list with all the tickers
    :return:
    """
    if input_list is None or len(input_list) <= 1:
        return [] if input_list is None else input_list[:]

    buckets = {}
    pivot = input_list[len(input_list) // 2]
    for val in input_list:
        if val is pivot:
            continue

        cur_set = frozenset([pivot, val])
        data = pytrends_wrapper.get(cur_set)

        diff = data[val].max() - data[pivot].max()
        # positive means val > pivot
        # negative means val < pivot
        # diff range: -100 to 100 -- 201 values in total

        buckets.setdefault(diff, []).append(val)

    buckets |= {key: optimized_sort(pytrends_wrapper, val) for key, val in buckets.items() if abs(key) > 95}
    buckets.setdefault(0, []).append(pivot)  # insert the pivot in 0 bucket
    buckets = sorted(buckets.items(), key=lambda x: x[0], reverse=True)
    # Sorting buckets in descending order
    # Each bucket should have its content already sorted in descending order
    # The key function might be a little unnecessary because the key will be compared first anyway
    # and all the keys are unique.

    return [item for key, bucket in buckets for item in bucket]
    # Unwrap the dict[int,list[str]] to a list[str]


def evaluate_data(pytrends_wrapper: PyTrendsWrapper, input_list: list[str]) -> pd.DataFrame:
    """
    Compares each ticker with the next, progressively, to build the relative weights
    :param pytrends_wrapper: The pytrends wrapper
    :param input_list: The input list with all the tickers
    :return: A DataFrame after all the re-weighting
    """
    def concat_data(data, column):
        return pd.concat([data, column.astype(float)], axis=1)

    data = None
    for i, val in enumerate(input_list):
        if i == len(input_list) - 1:
            cur_data = pytrends_wrapper.get(frozenset([val]))
            data = concat_data(data, cur_data[val])
            continue

        next_val = input_list[i + 1]
        cur_data = pytrends_wrapper.get(frozenset([val, next_val]))

        data = concat_data(data, cur_data[val])
        data = data.multiply(cur_data[val].max() / cur_data[next_val].max())

    return data


def eliminate_empty(pytrends_wrapper: PyTrendsWrapper, input_list: list[str]) -> tuple[list[str], list[str]]:
    """
    Eliminates the tickers with the empty Google Trends data
    :param pytrends_wrapper: The pytrends wrapper
    :param input_list: The input list with all the tickers
    :return: The tickers with some data and the tickers with no data in separate lists
    """
    input_deque = collections.deque(input_list)
    output = []
    empty = []

    while input_deque:
        cur_list = [input_deque.popleft() for _ in range(5) if input_deque]

        data = pytrends_wrapper.get(frozenset(cur_list))

        # There is no Google Trends data for this search
        if data is None or data.empty:
            empty.extend(cur_list)
            continue

        for item in cur_list:
            if data[item].max() != 0:
                output.append(item)
            else:
                input_deque.append(item)

    return output, empty


def parse_input() -> tuple[list[str], dict[str, Any], dict[str, Any]]:
    parser = argparse.ArgumentParser(description="Collect Data From Google Trends")

    # Arguments for input list
    parser.add_argument("input_file", metavar="input-file", type=str,
                        help="Path of the input file (header-less, one-column, csv file)")
    parser.add_argument("-n", type=int, default=-1, help="Number of lines to read from file (default all)")

    # Arguments for Pytrends Connection
    parser.add_argument("--retries", type=int, default=3, help="PyTrends Connection Retry Number (default 3)",
                        choices=[num for num in range(5)])
    # Proxy options
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--scraperapi-token", type=str, default=None,
                       help="PyTrends Connection -- Scraper Api token to use for proxy (default None)")
    group.add_argument("--proxies", type=str, default=None,
                       help="PyTrends Connection proxy list as a comma delimited string (default None)")

    # Arguments for PyTrends request
    parser.add_argument("--timeframe", type=str, default='all', help="PyTrends Request Timeframe (default all)")
    parser.add_argument("--cat", type=int, default=16, help="PyTrends Request Category (default 16 for news)")
    parser.add_argument("--gprop", type=str, default='',
                        help="PyTrends Request Google Property to filter for (default web search)")
    parser.add_argument("--geo", type=str, default=None, help="PyTrends Request Location (default worldwide)")

    args = parser.parse_args()

    logging.info(f"Arguments: {args}")

    # Loading the input
    input_list = pd.read_csv(args.input_file, header=None)[0].values.tolist()
    if 0 < args.n < len(input_list):
        input_list = input_list[:args.n]

    # Loading PyTrends Connection Arguments
    pytrends_kwargs = {
        'hl': 'en-US',
        'tz': 360,
        'retries': args.retries,
        'backoff_factor': 0.1,
        'timeout':(15,30)
    }
    if args.scraperapi_token:
        pytrends_kwargs['proxies'] = [f"http://scraperapi:{args.scraperapi_token}@proxy-server.scraperapi.com:8001"]
    elif args.proxies:
        pytrends_kwargs['proxies'] = args.proxies.split(",")
    
    if 'proxies' in pytrends_kwargs:
        pytrends_kwargs['requests_args'] = {'verify':False}
        urllib3.disable_warnings() # to disable warnings about using ssl

    # Loading PyTrends Request Arguments
    request_kwargs = {
        'timeframe': args.timeframe,
        'cat': args.cat,
        'gprop': args.gprop
    }
    if args.geo:
        request_kwargs['geo'] = args.geo

    return input_list, pytrends_kwargs, request_kwargs


def main():

    logging.basicConfig(filename='Collector.log', encoding='utf-8', level=logging.DEBUG)

    while(True):
        starttime = datetime.now()
        logging.info(f"Starting at {starttime}")

        input_list, pytrends_kwargs, request_kwargs = parse_input()

        logging.info(f"Input List Length: {len(input_list)}")
        logging.info(f"PyTrends Connection Kwargs: {pytrends_kwargs}")
        logging.info(f"PyTrends Request Kwargs: {request_kwargs}")
        try:
            pytrends_wrapper = PyTrendsWrapper(pytrends_kwargs, request_kwargs)
            input_list, empty = eliminate_empty(pytrends_wrapper, input_list)

            if "Tickers" in input_list: # FIXME: Delete later
                input_list.remove("Tickers")
            if "Tickers" in empty:
                empty.remove("Tickers")

            logging.info("Filtered the Input List")
            logging.info(f"Filtered Input List Length: {len(input_list)}")
            logging.info(f"No Data Tokens: {len(empty)}")
            logging.info(f"Number of PyTrends Requests After Filtering: {pytrends_wrapper.call_count}")

            # Save the tokens which are not found in google trends
            pd.DataFrame(empty, columns=["No Data Tokens"]).to_csv('empty.csv', index=False)

            logging.info("Saved the empty tokens")

            if not input_list:
                logging.error("No Valid Tokens -- none of the tokens have google trends data")
                break 
            
            sorted_input = optimized_sort(pytrends_wrapper, input_list)

            logging.info("Sorted the Input List")
            logging.info(f"Number of PyTrends Requests After Sorting: {pytrends_wrapper.call_count}")
            
            data = evaluate_data(pytrends_wrapper, sorted_input)

            logging.info("Evaluated the Input List")
            logging.info(f"Number of PyTrends Requests After Evaluating the Data: {pytrends_wrapper.call_count}")
            logging.info(f"Data Shape: {data.shape}")

            # Save the output
            data.to_csv("output.csv")
            logging.info("Saved the output")
            logging.info(f"Done at {datetime.now()}")
            logging.info(f"Total Time: {datetime.now() - starttime}")
            break
        except KeyboardInterrupt:
            logging.info("Keyboard Interrupt: Quitting")
            print("Keyboard Interrupt: Quitting")
            break
        except Exception as e:
            logging.error(f"Exception: {e}")
            logging.error(f"Looping Again-- nay, exiting")
            exit()
            time.sleep(5)
            continue

if __name__ == "__main__":
    main()
