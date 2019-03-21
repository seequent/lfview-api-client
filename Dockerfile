FROM python:3.6
MAINTAINER "Franklin Koch <franklin.koch@seequent.com>"

RUN mkdir -p /usr/src/app
WORKDIR /usr/src/app

COPY requirements.txt requirements_dev.txt setup.py README.rst Makefile /usr/src/app/
RUN pip install -r requirements_dev.txt
COPY lfview /usr/src/app/lfview
COPY docs /usr/src/app/docs
