FROM python:latest

RUN apt-get update -y && apt-get upgrade -y

RUN pip install redis pandas pytrends pyyaml

COPY . /
