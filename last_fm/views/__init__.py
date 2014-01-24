# -*- coding: utf-8 -*-
from __future__ import absolute_import, unicode_literals

from datetime import datetime
from flask.ext.login import current_user
from sqlalchemy.sql import func

from last_fm.app import app
from last_fm.db import db

from last_fm.views.analytics import *
from last_fm.views.conky import *
from last_fm.views.index import *
from last_fm.views.login import *
from last_fm.views.usercp import *


@app.context_processor
def context_processor():
    context = {}

    context["now"] = datetime.now()

    if current_user.is_authenticated():
        context["current_user_scrobble_count"] = db.session.query(func.count(Scrobble)).\
                                                            filter(Scrobble.user == current_user).\
                                                            scalar()

    return context
