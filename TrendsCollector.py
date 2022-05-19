from importlib.abc import Loader
from unicodedata import name
from pytrends.request import TrendReq
import pandas as pd
import yaml
import collections

class PyTrends_Wrapper:

    def __init__(self, pytrends, pytrends_kwargs):
        self.cache_filename = "cache.yaml"
        self.pytrends = pytrends
        self.pytrends_kwargs = pytrends_kwargs
        
        self.cache = {}
        try:
            with open(self.cache_filename, "r") as file:
                self.cache = yaml.load(file, Loader=yaml.Loader)
        except:
            pass
        
        if not isinstance(self.cache, dict):
            self.cache = {}

    def __del__(self):
        with open(self.cache_filename, "w") as file:
            yaml.dump(self.cache, file, Dumper=yaml.Dumper)

    def get(self, key: frozenset[str]) -> pd.DataFrame:
        if not key in self.cache:
            pytrends.build_payload(key, **self.pytrends_kwargs)
            self.cache[key] = pytrends.interest_over_time()
        return self.cache[key]

def optimized_sort(pytrends_wrapper: PyTrends_Wrapper, input_list: list[str]):
    if(input_list is None or len(input_list) <= 1):
        return [] if input_list is None else input_list[:]

    buckets = {}
    pivot = input_list[len(input_list) // 2]
    for val in input_list:
        if val is pivot:
            print("Reached Mid")
            continue

        cur_set = frozenset([pivot,val])
        data = pytrends_wrapper.get(cur_set)

        diff = data[val].max() - data[pivot].max()
        # positive means val > pivot
        # negative means val < pivot
        #-100 to 100 --> 201

        buckets.setdefault(diff, []).append(val)
    
    buckets = {key:optimized_sort(cache, pytrends, pytrends_kwargs, val) for key, val in buckets.items()}
    buckets.setdefault(0, []).append(pivot) # insert the pivot in 0 bucket
    buckets = sorted(buckets.items(), key=lambda x: x[0], reverse=True) # Sorting in descending order
    # the key function might be a little unnecessary because the key will be compared first anyway and all the keys are unique.

    return [item for key, bucket in buckets for item in bucket]

def evaluate_data(pytrends_wrapper: PyTrends_Wrapper, input_list: list[str]):
    if not input_list:
        return None

    def concat_data(data, column):
        return pd.concat([data, column.astype(float)], axis=1)

    data = None
    for i, val in enumerate(input_list):
        if i == len(input_list) - 1:
            cur_data = pytrends_wrapper.get(frozenset(val))
            data = concat_data(data,cur_data[val])
            continue

        next_val = input_list[i+1]
        cur_data = pytrends_wrapper(frozenset([val, next_val]))
        data = concat_data(data,cur_data[val])
        data = data.multiply(cur_data[val].max()/cur_data[next].max())
        
    return data

def eliminate_empty(pytrends_wrapper: PyTrends_Wrapper, input_list: list[str]) -> list[str]:

    input_deque = collections.deque(input_list)
    output = []

    while input_deque:
        cur_set = frozenset(input_deque.popleft() for i in range(5) if input_deque)
        
        data = pytrends_wrapper.get(cur_set)
        
        # There is no Google Trends data for this search
        if data is None or data.empty:
            continue

        for item in cur_set:
            if data[item].max() != 0:
                output.append(item)
            else:
                input_deque.append(item)
    
    return output

if __name__ == "__main__":

    pytrends = TrendReq(hl='en-US', tz=360, retries=3)
    pytrends_kwargs = {'timeframe':'all', 'cat':16, 'gprop':'news'}
    pytrends_wrapper = PyTrends_Wrapper(pytrends, pytrends_kwargs)

    input_list = pd.read_csv('input/input.csv', header=None)[0].values.tolist()[0:1000]
    print("Input: ", input_list)

    input_list = eliminate_empty(pytrends_wrapper, input_list)
    print("Cleaned Input: ", input_list)

    sorted_input = optimized_sort(pytrends_wrapper, input_list)
    print("Sorted: ", sorted_input)

    data = evaluate_data(sorted_input)
    data.to_csv("output.csv")
    print(data)
    
