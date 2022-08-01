# Getting Started

This is a tool to collect data from Google Trends. It helps overcome Google Trends's limitations of only comparing 5 search terms and that each comparison is relative.

## Setup

To setup this tool, you need [Docker](https://docs.docker.com/get-started/). If you use Linux and didn't install Docker Desktop, you might need to install [Docker compose](https://docs.docker.com/compose/install/) separately.

Clone or download the repository.

```bash
$ git clone https://github.com/Youssef-Beltagy/GoogleTrends-DataCollector.git
```

Then build the docker containers

```bash
$ docker-compose up -d
```

## Run

To run the program, you need a one-column csv file of all the keywords you want to compare. There shouldn't be a header in that file. Copy that file into this program's directory.

Then you can get terminal access to the docker container of the tool.

```bash
$ docker exec -it trends_collector bash # Get interactive terminal access to the container
```

Once you get terminal access to the container, move to the program's directory and run the program.

```bash
$ cd collector-dir # move to the program directory inside the container
$ python TrendsCollector.py sample_input.csv # run the program and pass it the input file name
```
At the end, you should get an output directory with four files
- output.csv, the Google Trends data
- empty.csv, all the search terms which Google Trends didn't have data for
- Collector.log, the log of this program
- cache.rdb, a snapshot of the redis database as a backup for intermediate results

To quit execution of the TrendsCollector, type Ctrl-C.

## Cleanup

Run this command on your machine (not inside the docker image) to take down the containers and their images.

```
$ docker-compose down --rmi all
```

It is recommended to delete the cache.rdb file as well so it is not accidentally used in future iterations (see #changing-values).

## Troubleshooting

How to handle common errors.

### Changing Values

When you run this program, if your time frame includes the current dates, the values might not be finalized. For example, if you are searching up to the current month when you are at the beginning of the month. Google Trends reports partial values (values that have not been finalized) in these cases.

If you rerun the program again later without deleting the cache, the old values in the cache might conflict with the new values. They might have less rows (because the time frame was shorter) or the data may simply be inconsistent (because some values were retrieved at the end of the month while others were retrieved at the beginning). In both of these situations, the recommended solution is to cleanup the project (see #cleanup), delete the cache.rdb file, and rerun the program.

### Retry Errors

If the program exits because of retry errors, the reason is likely that Google started throttling requests from your ip. The best way to overcome this issue is to use a vpn like nordvpn and change your ip address. Alternatively, you can simply wait for 4-6 hours or pass a list of proxy servers as an argument to this program. However, proxy servers significantly slowed down this program's execution and reduced its reliability.

You can then rerun the program. Intermediate values are saved in the redis database between program iterations. And even if you remove the docker containers, the redis database will be rebuilt from the snapshot in the output directory.

## Help

This is the help prompt of this program.

```bash
$ python TrendsCollector.py --help
usage: TrendsCollector.py [-h] [-n N] [--four-col] [--retries {0,1,2,3,4}]
                          [--scraperapi-token SCRAPERAPI_TOKEN | --proxies PROXIES] [--timeframe TIMEFRAME] [--cat CAT]
                          [--gprop GPROP] [--geo GEO]
                          input-file

Collect Data From Google Trends

positional arguments:
  input-file            Path of the input file (header-less, one-column, csv file)

optional arguments:
  -h, --help            show this help message and exit
  -n N                  Number of lines to read from file (default all)
  --four-col            produce the output in four column format
  --retries {0,1,2,3,4}
                        PyTrends Connection Retry Number (default 3)
  --scraperapi-token SCRAPERAPI_TOKEN
                        PyTrends Connection -- Scraper Api token to use for proxy (default None)
  --proxies PROXIES     PyTrends Connection proxy list as a comma delimited string (default None)
  --timeframe TIMEFRAME
                        PyTrends Request Timeframe (default all)
  --cat CAT             PyTrends Request Category (default 16 for news)
  --gprop GPROP         PyTrends Request Google Property to filter for (default web search)
  --geo GEO             PyTrends Request Location (default worldwide)
```
