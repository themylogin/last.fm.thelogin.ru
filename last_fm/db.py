# -*- coding: utf-8 -*-
from __future__ import absolute_import, unicode_literals

from flask.ext.sqlalchemy import SQLAlchemy

from last_fm.app import app

db = SQLAlchemy(app)
