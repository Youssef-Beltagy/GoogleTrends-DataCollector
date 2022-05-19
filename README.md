# Google Trends Data Collection

Collect data from Google Trends while minimizing zeros

Motivation:
- To measure overconfidence
- Person may become more overconfident by seeing higher google trends count

## Approach
Input:
- Excel Sheet of Stocks
- Category: news
- News search
- For whole world
- For all time
- Granularity of time? --> monthly for the most part
- Granularity of values? --> don't worry too much

Output:
- Excel Sheet
- Rows represent dates
- Columns represent a stock

Approach:
- Eliminate invalid searches
- Sort the values using pivot sort
- Compare the values one by one

Limitations:
- Within a single company, you still see zeros when those "zeros" might in fact be bigger than other the maximum of other companies.
- It is not straight forward to guarantee absolute correctness because rounding may mess with the results

Challenges:
- Google Trends doesn't have an api
- Google Trends doesn't provide absolute values -- everything is relative
- Only five items can be compared at a time
- Smaller values are scaled to zero
- **DataSet is bigger than expected** --> 15,200 unique stocks
  - Also discuss input format
- **Empty Values**:
  - NYSE:ALO.2 and NYSE:AVX How to handle that? https://trends.google.com/trends/explore?geo=US&q=NYSE%20ALO.2,NYSE%20AVX
  - All these have empty values: NYSE:ALO.2, NYSE:UDI., NYSE:ASA, NYSE:AVX
  - In fact, everything in the first hundred except: NYSE:AIG, NYSE:AIR, NYSE:ADM, NYSE:ABT, NYSE:PRI, NYSE:Y, NYSE:ALK, NYSE:AXP
  - What are these periods in stock names?
- **Topics vs Search Terms**:
  - Google search term vs topic: https://trends.google.com/trends/explore?geo=US&q=%2Fm%2F07zln7n,NASDAQ:googl
  - Google Search Term vs Topic vs General: https://trends.google.com/trends/explore?geo=US&q=%2Fm%2F07zln7n,%2Fm%2F07zln7n,nasdaq%20googl,google
  - Colon idea won't always work -- in fact, might bring even more zeros
  - It might be better to limit the category to finance
- **Google's Rate Limit**
  - After making some web calls, google starts to block me
  - We can mitigate this issue by optimizing the code a little (using a cache)
  - I can also look into using proxies
- **Speed**
  - The computation itself is not an issue, but because network calls are slow and Google starts throttling/limiting calls, the program may be slow
  - This problem can be mitigated 
- Maybe Memory

## Resources
Documentation: https://pypi.org/project/pytrends/
Short PyTrends guide: https://lazarinastoy.com/the-ultimate-guide-to-pytrends-google-trends-api-with-python/
Short PyTrends Demos:
- https://hackernoon.com/how-to-use-google-trends-api-with-python
- https://blog.devgenius.io/learn-how-to-easily-pull-google-trends-data-with-python-code-e52523c6ac1d
Pandas: https://pandas.pydata.org/docs/user_guide/10min.html
Yaml dump/load works for data frames -- can be used to store values on error
Proxy:
- https://www.linkedin.com/pulse/how-eat-google-trends-python-real-time-igor-miazek/
- https://www.scraperapi.com/blog/best-10-free-proxies-and-free-proxy-lists-for-web-scraping/

## Next Steps:

Proposed next steps:

Optimizations:
- Run the program again after google allows me + review output more thoroughly - https://trends.google.com/trends/explore?cat=16&date=all&q=nasdaq%20air,nasdaq:air
- Review the code and identify bottlenecks + review assumptions
- Brainstorm more optimized solutions
- Use better search parameters

```python
# Sort using groups of four but in 2 buckets
# log(8785)/log(2) * 8785 = 115090.761425
# log(8785)/log(2) * 8785 / 4 = 28772.6903563

# Sort using groups of 2 but in 200 buckets
# log(8785)/log(200)*8785 = 15056.6361491

# Comparison
#   the numerators are the same so what matters are the denominators
# 1/(log(2) * 4) > 1/log(200)
# 0.83048202372 > 0.43458798967

# # Eliminating data
# Currently comparing 5 items at a time
# 
# # Sorting  
# Use four tickers in each call
# group into 200 lists <-- currently used
    # Further, only sort the -100 and the 100 buckets
    # or buckets with abs(diff) > 90
    # Sorting the 0 bucket is especially useless and the way the pivot is inserted in the zero bucket is a little bit of an edge case.
# 
# # Evaluating
# Currently evaluating 1 by 1 for maximum resolution
# Can be optimized by comparing 5 items at a time

# # Implemented the PyTrends Wrapper to abstract away the PyTrends calling and caching logic
# Cache was around 1.6 MegaBytes for 100 items in the data set
# Cache might become ~100 MegaBytes for all ~9000 items in the data set
```

API Call Limits: 7hrs
- Experiment with disconnecting/reconnecting
- Investigate using proxies
- Experiment with proxies

- Works
  - "http://scraperapi:<your-token>@proxy-server.scraperapi.com:8001"
- Doesn't Work:
  - https://spys.one/en/
  - https://openproxy.space/list/http
  - Geonode
  - https://proxyscrape.com/free-proxy-list
  - https://www.proxy-list.download/
- Can try:
  - http://free-proxy.cz/en/ -- a little hard to test because programmatic access is inconvenient
  - https://www.freeproxylists.net/ -- a little hard to test because programmatic access is inconvenient
  - https://www.proxy-list.download/HTTP
  - https://proxyscrape.com/free-proxy-list can try paid
  - https://www.sslproxies.org/ can try paid
  - https://www.proxynova.com/proxy-server-list -- a little hard to test programmatic access is inconvenient

```python

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

```

Validation:
- Ensure output is satisfactory
- Refactor code for clarity
- Make CLI