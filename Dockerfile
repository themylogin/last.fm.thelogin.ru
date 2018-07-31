FROM ubuntu:16.04

RUN apt-get update && \
    apt-get -y install python \
                       python-dev \
                       python-numpy \
                       python-scipy \
                       python-pip \
                       python-virtualenv \
                       libjpeg-dev \
                       libpng-dev \
                       libpq-dev \
                       libxml2-dev \
                       libxslt-dev

RUN python -m virtualenv --python=python --system-site-packages /virtualenv

ADD requirements.txt /requirements.txt
RUN /virtualenv/bin/pip install -r /requirements.txt

RUN mkdir /last_fm
RUN mkdir /last_fm/last_fm
RUN touch /last_fm/last_fm/__init__.py
ADD setup.py /last_fm/setup.py

WORKDIR /last_fm
RUN /virtualenv/bin/pip install "https://github.com/themylogin/themyutils/zipball/master#egg=themyutils"
RUN /virtualenv/bin/pip install "https://github.com/themylogin/twitter-overkill/zipball/master#egg=twitter-overkill"
RUN /virtualenv/bin/python setup.py develop

RUN rm -rf /last_fm/last_fm
ADD alembic.ini /last_fm/alembic.ini
ADD alembic /last_fm/alembic
ADD last_fm /last_fm/last_fm
