# -*- coding: utf-8 -*-
from __future__ import absolute_import, division, unicode_literals

from flask.ext.bootstrap import Bootstrap
from raven import Client
from raven.contrib.celery import register_signal, register_logger_signal
from raven.contrib.flask import Sentry
from redis import Redis
import socket
import sys
from werkzeug.exceptions import HTTPException

from themyutils.flask.redis_session import RedisSessionInterface

from last_fm.app import app
from last_fm.cache import cache
from last_fm.celery import celery
from last_fm.db import db
from last_fm.login_manager import login_manager
from last_fm.models import *
from last_fm.redis import redis

socket.setdefaulttimeout(10)

Bootstrap(app)
login_manager.init_app(app)
app.session_interface = RedisSessionInterface(redis=redis, prefix="last.fm:session:")

runner = sys.argv[0].split("/")[-1]
if runner in ["celery", "gunicorn", "uwsgi"]:
    app.config["RAVEN_IGNORE_EXCEPTIONS"] = [HTTPException]

    sentry = Sentry(app, wrap_wsgi=runner != "gunicorn")

    sentry_client = Client(app.config["SENTRY_DSN"])
    register_logger_signal(sentry_client)
    register_signal(sentry_client)

import last_fm.api
import last_fm.cron
import last_fm.hacks
import last_fm.views
