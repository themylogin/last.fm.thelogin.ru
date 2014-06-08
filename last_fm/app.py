# -*- coding: utf-8 -*-
from __future__ import absolute_import, unicode_literals

from flask import Flask
from raven.contrib.flask import Sentry
from werkzeug.exceptions import HTTPException

import last_fm.config

app = Flask("last_fm")
app.config.from_object(last_fm.config)
app.config["RAVEN_IGNORE_EXCEPTIONS"] = [HTTPException]

sentry = Sentry(app)
