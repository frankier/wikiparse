FROM python:3.7-alpine

RUN apk --no-cache --update-cache add gcc gfortran python python-dev py-pip build-base wget freetype-dev libpng-dev openblas-dev curl
RUN ln -s /usr/include/locale.h /usr/include/xlocale.h

RUN ln -sf /usr/bin/python3 /usr/bin/python
RUN curl -sSL https://raw.githubusercontent.com/sdispater/poetry/master/get-poetry.py | python3
ENV PATH="~/.poetry/bin/:${PATH}"

RUN set -ex && mkdir /app && mkdir /app/wikiparse && touch /app/wikiparse/__init__.py

WORKDIR /app

COPY pyproject.toml pyproject.toml

RUN ~/.poetry/bin/poetry config virtualenvs.create false && \
    ~/.poetry/bin/poetry install

COPY . /app

CMD snakemake
