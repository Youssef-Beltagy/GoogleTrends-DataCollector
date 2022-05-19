from unicodedata import name
from pytrends.request import TrendReq
import pandas as pd
import yaml
import collections

def quick_sort(input_list: list[str], l: int, r: int):
    if(l >= r):
        return

    mid = (r - l)//2 + l
    temp = input_list[mid]
    input_list[mid] = input_list[r]
    input_list[r] = temp

    pivot = input_list[r]
    end_strictly_smaller = l - 1

    pytrends = TrendReq(hl='en-US', tz=360, retries=3, backoff_factor=1) # connect to google
    for i in range(l,r): # exclude r
        val = input_list[i]

        my_set = frozenset([pivot,val])
        if my_set not in cache:
            pytrends.build_payload([pivot, val], geo='US', timeframe='all', cat=7)
            cache[my_set] = pytrends.interest_over_time()
        data = cache[my_set]

        if data[pivot].max() > data[val].max():
            end_strictly_smaller += 1
            input_list[i] = input_list[end_strictly_smaller]
            input_list[end_strictly_smaller] = val    

    end_strictly_smaller += 1
    input_list[r] = input_list[end_strictly_smaller]
    input_list[end_strictly_smaller] = pivot
    
    quick_sort(input_list, l, end_strictly_smaller - 1)
    quick_sort(input_list, end_strictly_smaller + 1, r)

def sort_trends(input_list: list[str]) -> list[str]:
    output_list = input_list.copy()
    quick_sort(output_list, 0, len(output_list) - 1)
    return output_list


# FIXME: I can improve this function's output
def evaluate_data(input_list: list[str]):
    if not input_list:
        return None

    pytrends = TrendReq(hl='en-US', tz=360, retries=3, backoff_factor=1) # connect to google
    
    if len(input_list) == 1:
        val = input_list[0]
        if val not in cache:
            pytrends.build_payload([val], geo='US', timeframe='all', cat=7)
            cache[val] = pytrends.interest_over_time()
        data = cache[val][val].astype(float)
        return data

    data = None
    for i, val in enumerate(input_list):
        if i == len(input_list) - 1:
            pytrends.build_payload([val], geo='US', timeframe='all', cat=7)
            temp_data = cache[val]
            data = pd.concat([data,temp_data[val].astype(float)], axis=1)
            continue

        next = input_list[i+1]

        my_set = frozenset([val,next])
        if my_set not in cache:
            pytrends.build_payload([val, next], geo='US', timeframe='all', cat=7)
            cache[my_set] = pytrends.interest_over_time()
        temp_data = cache[my_set]
        data = pd.concat([data,temp_data[val].astype(float)], axis=1)
        data = data.multiply(temp_data[val].max()/temp_data[next].max())
        
    return data

def eliminate_empty(cache: dict, pytrends: TrendReq, pytrends_kwargs: dict, input_list: list[str]) -> list[str]:

    input_deque = collections.deque(input_list)
    output = []

    while input_deque:
        cur_set = frozenset(input_deque.popleft() for i in range(5) if input_deque)

        data = cache.get(cur_set, "Invalid")
        if isinstance(data, str) and data == "Invalid":
            pytrends.build_payload(cur_set, **pytrends_kwargs)
            data = cache.setdefault(cur_set, pytrends.interest_over_time())

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

    cache = {}
    pytrends = TrendReq(hl='en-US', tz=360, retries=3)
    pytrends_kwargs = {'timeframe':'all', 'cat':16, 'gprop':'news'}

    input_list = pd.read_csv('input/input.csv', header=None)[0].values.tolist()[0:100]
    input_list = eliminate_empty(cache, pytrends, pytrends_kwargs, input_list)
    # input_list = ["ABBY", "IFCI", "VOLT", "YNR", "UTOG", "SCTC", "ENTS", "ARST", "GROV", "AHII", "ACTL", "ENGA", "ALRT", "TKCI", "WSTR", "GTII", "ESSI", "MTEC", "AVEC", "EAGL", "TMXN", "ARSC", "PMBS", "AFFI", "ASPT", "TRII", "IPLY", "MMTC", "AVO", "BTSR", "CBEX", "CRYO", "BLPG", "CHMD", "MTST", "MDIN", "USCS", "GASE", "CANL", "MEDT", "ELRN", "CBIS", "FPMI", "TSSW", "CRGO", "NTRO", "BTHE", "SRNA", "OPNT", "RAYS", "OXYS", "JAMN", "BFRE", "INVS", "PRLX", "AREM", "PTIX", "AOLS", "IMII", "VRUS", "BNET", "PHYX", "SURE", "CRCL", "PLSB", "SSET", "CANN", "SMLR", "EDFY", "ARTH", "IDEA", "HRTT", "TENF", "TGLO", "BPMX", "BARZ", "ACLZ", "BMRA", "BTGI", "BIOC", "BRFH", "PBT", "REMI", "PBIO", "DMPI", "IVVI", "MMMB", "SBR", "CYRX", "BPT", "INOW", "SNES", "ATRX", "WWCA", "AZRX", "LOOP", "PDRT", "REFR", "EYEG", "MRVT"]

    print("Input: ", input_list)
    # sorted_input = sort_trends(input_list)
    # print("Sorted: ", sorted_input)
    # Two optimization approaches:  
    # group into 200 lists
    # Use four tickers in each call

    # sorted_input.reverse()
    # data = evaluate_data(sorted_input)
    # data.to_csv("output_1000.csv")
    # print(data)


















    # # Proxy Testing Code
    # proxies = []
    # # with open("http.txt") as file:
    # #     proxies = [f"https://{line.strip()}" for line in file.readlines()]
    # pytrends = 
    # pytrends.build_payload(["Machine Learning"], timeframe='all', cat=16, gprop='news') # cat=16 = news search, default geo location is world
    # data = pytrends.interest_over_time()
    # cache[frozenset(["Machine Learning", "potato"])] = data
    # yaml.dump(cache, open("cache.yaml", "w"))
    # print(data)

    # temp = yaml.load(open("cache.yaml", "r"), Loader=yaml.Loader)
    # print(temp)

