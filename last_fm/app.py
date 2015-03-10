# -*- coding: utf-8 -*-
from __future__ import absolute_import, division, unicode_literals

from flask import Flask

import last_fm.config

__all__ = [b"app"]

app = Flask("last_fm")
app.config.from_object(last_fm.config)
