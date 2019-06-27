# -*- coding: utf-8 -*-
from __future__ import absolute_import, unicode_literals

import os

SECRET_KEY = os.environ["SECRET_KEY"]

SENTRY_DSN = os.environ["SENTRY_DSN"]

CELERY_BROKER_URL = "amqp://rabbitmq"
CELERYD_HIJACK_ROOT_LOGGER = False

SQLALCHEMY_DATABASE_URI = "postgresql+psycopg2://last_fm:last_fm@postgres/last_fm"

CACHE_TYPE = "redis"
CACHE_REDIS_HOST = "redis"

LAST_FM_API_KEY = os.environ["LAST_FM_API_KEY"]
LAST_FM_API_SECRET = os.environ["LAST_FM_API_SECRET"]

TWITTER_CONSUMER_KEY = os.environ["TWITTER_CONSUMER_KEY"]
TWITTER_CONSUMER_SECRET = os.environ["TWITTER_CONSUMER_SECRET"]

WHAT_CD_USERNAME = os.environ["WHAT_CD_USERNAME"]
WHAT_CD_PASSWORD = os.environ["WHAT_CD_PASSWORD"]

GUESTS_DEVICES_RESOLVER = os.environ["GUESTS_DEVICES_RESOLVER"]
GUESTS_DEVICES_PREFIXES = os.environ["GUESTS_DEVICES_PREFIXES"].split(",")

SQL_API_CLIENTS = os.environ["SQL_API_CLIENTS"].split(",")

MPD_HOST = os.environ["MPD_HOST"]
DEBUG=True