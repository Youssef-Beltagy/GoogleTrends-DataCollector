# Google Trends Data Collection

This file was used while developing this program. It contains a draft of the requirements.

## Objective

Collect data from Google Trends while minimizing zeros

Motivation:
- To measure overconfidence
- Person may become more overconfident by seeing higher google trends count

## Specifications

### Input

- Excel Sheet of Stocks
- Category: news
- Web search
- For whole world
- For all time
- Granularity of time? --> monthly for the most part
- Granularity of values? --> don't worry too much
- Join CSVs, Make column with stock exchange code
  - Assume No duplicates
  - In format <Stock>:<stock Exchange>

### Output

- Excel Sheet
- Rows represent dates
- Columns represent a stock

### Challenges
- Google Trends doesn't have an api
- Google Trends doesn't provide absolute values -- everything is relative
- Only five items can be compared at a time
- Smaller values are scaled to zero
- DataSet is bigger than expected --> 15,200 unique stocks
- Empty Values
  - NYSE:ALO.2 and NYSE:AVX How to handle that? https://trends.google.com/trends/explore?geo=US&q=NYSE%20ALO.2,NYSE%20AVX
  - All these have empty values: NYSE:ALO.2, NYSE:UDI., NYSE:ASA, NYSE:AVX
- Topics vs Search Terms
  - Google search term vs topic: https://trends.google.com/trends/explore?geo=US&q=%2Fm%2F07zln7n,NASDAQ:googl
  - Google Search Term vs Topic vs General: https://trends.google.com/trends/explore?geo=US&q=%2Fm%2F07zln7n,%2Fm%2F07zln7n,nasdaq%20googl,google
  - Colon idea won't always work -- in fact, might bring even more zeros
- Google's Rate Limit
  - After making some web calls, google starts to throttle
  - We can mitigate this issue by optimizing the code a little (using a cache)
  - I can also look into using proxies
- Speed
  - The computation itself is not an issue, but because network calls are slow and Google starts throttling/limiting calls, the program may be slow
  - This problem can be mitigated 
- Maybe Memory

### Approach

To get programmatic access to Google Trends, use PyTrends.

To bypass google's throttling use proxies or vpn. To ensure data is not lost during iterations, use a cache. File cache was unreliable so switched to redis.

- Eliminate invalid searches (search terms with no Google Trends data)
- Sort the values using pivot sort
  - An optimized pivot that uses 200 buckets is ~7.6 times faster (and makes less web calls) than using 2 buckets
  - Even then, only sort buckets with abs value above 95.
- Compare the values one by one to generate the output

Limitations:
- Within a single company, you still see zeros when those "zeros" might in fact be bigger than other the maximum of other companies.
- It is not straightforward to guarantee absolute correctness because rounding may mess with the results

## Resources

The code has two main dependencies: Redis and PyTrends. You can find more information on both here. It is especially worthwhile to look at PyTrends since this project is mostly a wrapper around it and many of Pytrends's arguments are relevant.

PyTrends:
- https://pypi.org/project/pytrends/
- https://lazarinastoy.com/the-ultimate-guide-to-pytrends-google-trends-api-with-python/
- https://hackernoon.com/how-to-use-google-trends-api-with-python
- https://blog.devgenius.io/learn-how-to-easily-pull-google-trends-data-with-python-code-e52523c6ac1d
- https://www.linkedin.com/pulse/how-eat-google-trends-python-real-time-igor-miazek/
Pandas:
- https://pandas.pydata.org/docs/user_guide/10min.html
Redis:
- https://realpython.com/python-redis/#using-redis-py-redis-in-python
- https://redis.io/docs/getting-started/
- https://betterprogramming.pub/dockerizing-and-pythonizing-redis-41b1340979de




