# -*- coding=utf-8 -*-
from __future__ import absolute_import, division, unicode_literals

from flask.ext.script import Manager

from last_fm.app import app

__all__ = [b"manager"]

manager = Manager(app)
