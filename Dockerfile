FROM python:3.7-alpine

RUN apk --no-cache --update-cache add gcc gfortran python python-dev py-pip build-base wget freetype-dev libpng-dev openblas-dev
RUN ln -s /usr/include/locale.h /usr/include/xlocale.h
RUN pip3 install pipenv

RUN set -ex && mkdir /app && mkdir /app/wikiparse

WORKDIR /app

COPY Pipfile Pipfile
COPY Pipfile.lock Pipfile.lock
COPY setup.py setup.py

RUN set -ex && pipenv install --deploy --system

COPY . /app

CMD python3 parse.py
