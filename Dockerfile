FROM python:3.7-buster

RUN apt-get update && apt-get install -y \
        # Build base
        gcc gfortran build-essential wget curl \
        # Python stuff
        python3 python3-dev python3-pip \
        # Graphviz
        graphviz libgraphviz-dev \
        # HFST package
        hfst python3-libhfst \
 && rm -rf /var/lib/apt/lists/*

RUN ln -sf /usr/bin/python3 /usr/bin/python
RUN curl -sSL https://raw.githubusercontent.com/sdispater/poetry/master/get-poetry.py | python3
ENV PATH="~/.poetry/bin/:${PATH}"

RUN set -ex && mkdir /app && mkdir /app/wikiparse && touch /app/wikiparse/__init__.py

WORKDIR /app

COPY pyproject.toml pyproject.toml

RUN ~/.poetry/bin/poetry config virtualenvs.create false && \
    ~/.poetry/bin/poetry install

RUN echo "/usr/lib/python3/dist-packages/" > /usr/local/lib/python3.7/site-packages/hfst.pth

COPY . /app

CMD snakemake
