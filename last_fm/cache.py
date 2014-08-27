# -*- coding: utf-8 -*-
from __future__ import absolute_import, division, unicode_literals

from flask.ext.cache import Cache

from last_fm.app import app

__all__ = [b"cache"]

cache = Cache(app)
