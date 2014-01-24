# -*- coding: utf-8 -*-
from __future__ import absolute_import, unicode_literals

from flask.ext.cache import Cache

from last_fm.app import app

cache = Cache(app)
