FROM python:3.7-alpine

RUN pip3 install pipenv

RUN set -ex && mkdir /app && mkdir /app/wikiparse

WORKDIR /app

COPY Pipfile Pipfile
COPY Pipfile.lock Pipfile.lock
COPY setup.py setup.py

RUN set -ex && pipenv install --deploy --system

COPY . /app

CMD python3 parse.py
