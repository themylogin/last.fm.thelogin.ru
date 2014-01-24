# -*- coding: utf-8 -*-
from __future__ import absolute_import, unicode_literals

from flask import Flask
from raven.contrib.flask import Sentry

import last_fm.config

app = Flask("last_fm")
app.config.from_object(last_fm.config)

sentry = Sentry(app)
