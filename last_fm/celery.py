# -*- coding=utf-8 -*-
from __future__ import absolute_import, division, unicode_literals

from themyutils.celery.beat import Cron
from themyutils.flask.celery import make_celery

from last_fm.app import app
from last_fm.db import db

__all__ = [b"celery", b"cron"]

celery = make_celery(app, db)
cron = Cron(celery)
