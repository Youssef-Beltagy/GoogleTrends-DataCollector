import collections
import argparse
import yaml
import logging
import redis
import pandas as pd
import urllib3

from urllib3.exceptions import MaxRetryError
from requests.exceptions import RetryError
from datetime import datetime
from typing import Any
from pytrends.request import TrendReq





class PyTrendsWrapper:
    """
    A wrapper over pytrends that caches results into a redis database
    """

    def __init__(self, pytrends_kwargs: dict[str, Any], request_kwargs: dict[str, Any]):
        """
        Constructor

        Args:
            pytrends_kwargs (dict[str, Any]): The keyword arguments to be passed to pytrends on initialization
            request_kwargs (dict[str, Any]):  The keyword arguments to be passed to pytrends on payload build
        """

        self.pytrends_kwargs = pytrends_kwargs.copy()
        self.request_kwargs = request_kwargs.copy()
        self.pytrends = TrendReq(**pytrends_kwargs)
        self.call_count = 0

        self.redis_cache = redis.Redis("redis") # connect to the redis container
        self.key_prefix = "Request Arguments: [" + ", ".join(str(t) for t in sorted(self.request_kwargs.items())) + "] -- "

    def get(self, key: frozenset[str]) -> pd.DataFrame:
        """
        Retrieves cache values for the key or Gets the data from PyTrends if the value is not cached
        
        Args:
            key (frozenset[str]): The set of arguments to lookup

        Returns:
            pd.DataFrame: A DataFrame with the resulting data
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

def optimized_sort(pytrends_wrapper: PyTrendsWrapper, input_list: list[str]) -> list[str]:
    """
    Partially sorts input_list based on their max GoogleTrends data

    Args:
        pytrends_wrapper (PyTrendsWrapper): The pytrends wrapper to make requests with
        input_list (list[str]): The input list with all the tickers

    Returns:
        list[str]: The partially sorted list
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

        # get the diff between the val and pivot to determine the target bucket
        # diff range: -100 to 100 -- 201 values in total
        # positive means val > pivot
        # negative means val < pivot
        diff = data[val].max() - data[pivot].max()
        buckets.setdefault(diff, []).append(val)

    # sort the content of each bucket
    buckets |= {key: optimized_sort(pytrends_wrapper, val) for key, val in buckets.items() if abs(key) > 95}

    # insert the pivot in 0 bucket
    buckets.setdefault(0, []).append(pivot) 

    # Sorting buckets in descending order
    # The key function might be a little unnecessary because the key will be compared first anyway
    # and all the keys are unique.
    buckets = sorted(buckets.items(), key=lambda x: x[0], reverse=True)    

    # Unwrap the dict[int,list[str]] to a list[str]
    return [item for key, bucket in buckets for item in bucket]
    


def evaluate_data(pytrends_wrapper: PyTrendsWrapper, input_list: list[str]) -> pd.DataFrame:
    """
    Compares each ticker with the next to build the relative weights.

    Args:
        pytrends_wrapper (PyTrendsWrapper): The pytrends wrapper to make requests with
        input_list (list[str]): The input list with all the tickers

    Returns:
        pd.DataFrame: A DataFrame with absolute weights inferred from Google Trends's relative weights
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

    Args:
        pytrends_wrapper (PyTrendsWrapper): The pytrends wrapper to make requests with
        input_list (list[str]): The input list with all the tickers

    Returns:
        tuple[list[str], list[str]]: The tickers with data and the tickers with no data in separate lists
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
                # Try again because the value may not really be zero and may in fact be rounded to zero.
                input_deque.append(item)

    return output, empty


def format_four_col(data: pd.DataFrame) -> pd.DataFrame:
    """
    Formats the output in four columns (date, exchange, stock symbol, google trends value)

    Args:
        data (pd.DataFrame): The output data frame with every row representing a date and
            every column representing a stock symbol in format <exchange>:<stock symbol>

    Returns:
        pd.DataFrame: The output data frame formatted in four columns
    """

    output = None
    for symbol in data.columns:
        exchange, ticker = symbol.split(":")

        df = pd.DataFrame({
            "exchange":exchange,
            "ticker":ticker,
            "google trends score":data[symbol]
        })

        df.reset_index(inplace=True)

        output = pd.concat([output, df], axis=0, ignore_index=True)

    return output

def parse_input() -> tuple[list[str], dict[str, Any], dict[str, Any], bool]:
    """
    Parses the command lines arguments

    Returns:
        tuple[list[str], dict[str, Any], dict[str, Any], Boolean]:
            the list is list of keywords to lookup in pytrends
            the first dictionary represents the keyword arguments to pass to pytrends on initialization
            the second dictionary represents the keyword arguments used in every pytrends call
            the boolean represents whether the output should be in a four column format
    """

    parser = argparse.ArgumentParser(description="Collect Data From Google Trends")

    # Arguments for input list
    parser.add_argument("input_file", metavar="input-file", type=str,
                        help="Path of the input file (header-less, one-column, csv file)")
    parser.add_argument("-n", type=int, default=-1, help="Number of lines to read from file (default all)")

    # Argument for output format
    parser.add_argument("--four-col", help="produce the output in four column format",
                    action="store_true")

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

    # Setting up proxies
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

    return input_list, pytrends_kwargs, request_kwargs, args.four_col

def main():
    """
    Generates absolute search frequency data from Google Trends.

    1. Parses the command line arguments
    2. Eliminates search keywords which Google Trends reports no values for
    3. Partially sorts the keywords using their max Google Trends score so
        adjacent keywords will have similar max Google Trends score
    4. Builds a dataframe of the absolute Google Trends Score inferred
        from the relative values Google Trends reports when comparing two keywords at a time
    """
    
    output_file_name = "output/output.csv"
    log_file_name = "output/Collector.log"

    logging.basicConfig(filename=log_file_name, encoding='utf-8', level=logging.DEBUG)

    starttime = datetime.now()
    logging.info(f"Starting at {starttime}")

    # 1. Parses the command line arguments
    input_list, pytrends_kwargs, request_kwargs, four_col = parse_input()

    logging.info(f"Input List Length: {len(input_list)}")
    logging.info(f"PyTrends Connection Kwargs: {pytrends_kwargs}")
    logging.info(f"PyTrends Request Kwargs: {request_kwargs}")
    logging.info(f"Saving Output in Four Columns: {four_col}")

    try:
        pytrends_wrapper = PyTrendsWrapper(pytrends_kwargs, request_kwargs)

        # 2. Eliminates search keywords which Google Trends reports no values for
        input_list, empty = eliminate_empty(pytrends_wrapper, input_list)

        logging.info("Filtered the Input List")
        logging.info(f"Filtered Input List Length: {len(input_list)}")
        logging.info(f"No Data Tokens: {len(empty)}")
        logging.info(f"Number of PyTrends Requests After Filtering: {pytrends_wrapper.call_count}")
        print("Filtered the Input List")

        # Save the tokens which are not found in google trends
        pd.DataFrame(empty, columns=["No Data Tokens"]).to_csv('output/empty.csv', index=False)

        logging.info("Saved the empty tokens")

        if not input_list:
            logging.error("No Valid Tokens -- none of the tokens have google trends data")
            print("None of the tokens has Google Trends Data\nCheck the log for more details")
            exit() 
        
        # 3. Partially sorts the keywords using their max Google Trends score so
        #   adjacent keywords will have similar max Google Trends score
        sorted_input = optimized_sort(pytrends_wrapper, input_list)

        logging.info("Sorted the Input List")
        logging.info(f"Number of PyTrends Requests After Sorting: {pytrends_wrapper.call_count}")
        print("Sorted the Input List")
        
        # 4. Builds a dataframe of the absolute Google Trends Score inferred
        #   from the relative values Google Trends reports when comparing two keywords at a time
        data = evaluate_data(pytrends_wrapper, sorted_input)

        logging.info("Evaluated the Data")
        logging.info(f"Number of PyTrends Requests After Evaluating the Data: {pytrends_wrapper.call_count}")
        logging.info(f"Data Shape: {data.shape}")
        print("Evaluated the Data")

        # Reformat the data (if needed) and save it
        if four_col:
            data = format_four_col(data)
            data.to_csv(output_file_name, index=False)
        else:
            data.to_csv(output_file_name)

        logging.info("Saved the output")
        logging.info(f"Done at {datetime.now()}")
        logging.info(f"Total Time: {datetime.now() - starttime}")
    except KeyboardInterrupt:
        logging.info("Keyboard Interrupt: Quitting")
        print("Keyboard Interrupt: Quitting")
    except (RetryError, MaxRetryError) as e:
        logging.error("Exited because of retry error")
        logging.error(f"Exception: {e}")
        logging.error("Google likely throttles requests from this ip now")
        logging.error("Change your ip with a vpn or a proxy")

        print("Exited because of retry error. Google likely throttles requests from this ip now.")
        print("Try again after changing your ip with a vpn or a proxy")
        print("Intermediate results should be cached in redis. So no data should be lost.")
    except Exception as e:
        logging.error(f"Unexpected Exception: {e}")
        
        print(e)
        print("Exited because of an unexpected exception.")
        print("Intermediate results should be cached in redis. So no data should be lost.")

if __name__ == "__main__":
    main()

