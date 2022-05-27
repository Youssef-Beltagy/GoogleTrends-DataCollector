import argparse
import collections
from typing import Any
import pandas as pd
import yaml
from pytrends.request import TrendReq
import os


class PyTrendsWrapper:
    CACHE_FILENAME = "cache.yaml"
    CACHE_REQUEST_ARGS_KEY = "__REQUEST_ARGUMENTS__"  # key of the request args in the cache

    def __init__(self, pytrends_kwargs: dict[str, Any], request_kwargs: dict[str, Any]):
        self.pytrends_kwargs = pytrends_kwargs.copy()
        self.request_kwargs = request_kwargs.copy()
        self.pytrends = TrendReq(**self.pytrends_kwargs)
        self.cache: dict[frozenset[str] | str, pd.DataFrame] = {}

        if os.path.exists(PyTrendsWrapper.CACHE_FILENAME):
            with open(PyTrendsWrapper.CACHE_FILENAME, "r") as file:
                self.cache = yaml.load(file, Loader=yaml.Loader)

        # ensure cache is dict and is using the current request args
        if (not isinstance(self.cache, dict)
                or PyTrendsWrapper.CACHE_REQUEST_ARGS_KEY not in self.cache
                or self.cache[PyTrendsWrapper.CACHE_REQUEST_ARGS_KEY] != self.request_kwargs):
            self.cache = {PyTrendsWrapper.CACHE_REQUEST_ARGS_KEY: self.request_kwargs}

        self.cache: dict[frozenset[str] | str, pd.DataFrame] = self.cache

    def __enter__(self):
        return self

    def __exit__(self, exception_type, exception_value, exception_traceback):
        with open(PyTrendsWrapper.CACHE_FILENAME, "w") as file:
            yaml.dump(self.cache, file, Dumper=yaml.Dumper)

    def get(self, key: frozenset[str]) -> pd.DataFrame:
        if key not in self.cache:
            self.pytrends.build_payload(key, **self.request_kwargs)
            self.cache[key] = self.pytrends.interest_over_time()
        return self.cache[key]


def optimized_sort(pytrends_wrapper: PyTrendsWrapper, input_list: list[str]):
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
    input_deque = collections.deque(input_list)
    output = []
    empty = []

    while input_deque:
        cur_set = frozenset(input_deque.popleft() for _ in range(5) if input_deque)

        data = pytrends_wrapper.get(cur_set)

        # There is no Google Trends data for this search
        if data is None or data.empty:
            empty.extend(cur_set)
            continue

        for item in cur_set:
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
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--scraperapi-token", type=str, default=None,
                       help="PyTrends Connection -- Scraper Api token to use for proxy (default None)")
    group.add_argument("--proxies", type=str, default=None,
                       help="PyTrends Connection proxy list as a comma delimited string (default None)")

    # Arguments for PyTrends request
    parser.add_argument("--timeframe", type=str, default='all', help="PyTrends Request Timeframe (default all)")
    parser.add_argument("--cat", type=int, default=16, help="PyTrends Request Category (default 16 for news)")
    parser.add_argument("--gprop", type=str, default='news',
                        help="PyTrends Request Google Property to filter for (default news)")
    parser.add_argument("--geo", type=str, default=None, help="PyTrends Request Location (default worldwide)")

    args = parser.parse_args()

    # Loading the input
    input_list = pd.read_csv(args.input_file, header=None)[0].values.tolist()
    if 0 < args.n < len(input_list):
        input_list = input_list[:args.n]

    # Loading PyTrends Connection Arguments
    pytrends_kwargs = {
        'hl': 'en-US',
        'tz': 360,
        'retries': args.retries
    }
    if args.scraperapi_token:
        pytrends_kwargs['proxies'] = [f"http://scraperapi:{args.scraperapi_token}@proxy-server.scraperapi.com:8001"]
    elif args.proxies:
        pytrends_kwargs['proxies'] = args.proxies.split(",")

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
    input_list, pytrends_kwargs, request_kwargs = parse_input()

    with PyTrendsWrapper(pytrends_kwargs, request_kwargs) as pytrends_wrapper:
        input_list, empty = eliminate_empty(pytrends_wrapper, input_list)

        # Save the tokens which are not found in google trends
        pd.DataFrame(empty, columns=["Not Found Tokens"]).to_csv('empty.csv', index=False)

        sorted_input = optimized_sort(pytrends_wrapper, input_list)

        if not sorted_input:
            raise ValueError("Could not generate input")

        data = evaluate_data(pytrends_wrapper, sorted_input)

        # Save the output
        data.to_csv("output.csv")


if __name__ == "__main__":
    main()
