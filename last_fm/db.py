# -*- coding: utf-8 -*-
from __future__ import absolute_import, division, unicode_literals

from flask.ext.sqlalchemy import SQLAlchemy

from last_fm.app import app

__all__ = [b"db"]

db = SQLAlchemy(app)
