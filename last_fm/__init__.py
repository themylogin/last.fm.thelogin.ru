# -*- coding: utf-8 -*-
from __future__ import absolute_import, division, unicode_literals

from flask.ext.bootstrap import Bootstrap

from themylog.client import setup_logging_handler
from themyutils.flask.redis_session import RedisSessionInterface

from last_fm.app import app
from last_fm.cache import cache
from last_fm.celery import celery
from last_fm.db import db
from last_fm.login_manager import login_manager
from last_fm.models import *

Bootstrap(app)
login_manager.init_app(app)
app.session_interface = RedisSessionInterface(prefix="last.fm:session:")

setup_logging_handler("last_fm")

import last_fm.api
import last_fm.cron
import last_fm.hacks
import last_fm.views
