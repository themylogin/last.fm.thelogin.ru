FROM ubuntu:16.04

RUN apt-get update

RUN apt-get -y install python \
                       python-dev \
                       python-pip \
                       python-virtualenv
    
RUN apt-get -y install libjpeg-dev \
                       libpng-dev \
                       libpq-dev \
                       libxml2-dev \
                       libxslt-dev

RUN python -m virtualenv --python=python /virtualenv

RUN /virtualenv/bin/pip install uwsgi

RUN mkdir /last_fm
RUN mkdir /last_fm/last_fm
RUN touch /last_fm/last_fm/__init__.py
ADD setup.py /last_fm/setup.py

WORKDIR /last_fm
RUN /virtualenv/bin/pip install Flask==0.11.1
RUN /virtualenv/bin/pip install numpy==1.11.1
RUN /virtualenv/bin/pip install scipy==0.18.0
RUN /virtualenv/bin/python setup.py develop

RUN rm -rf /last_fm/last_fm
ADD alembic.ini /last_fm/alembic.ini
ADD alembic /last_fm/alembic
ADD last_fm /last_fm/last_fm
