# -*- coding: utf-8 -*-
from __future__ import absolute_import, division, unicode_literals

from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
from flask.ext.login import current_user
import os
from pluralize import pluralize
from sqlalchemy.sql import func

from themyutils.datetime import russian_strftime
from themyutils.flask.controllers.image_server import ImageServer

from last_fm.app import app
from last_fm.db import db
from last_fm.models import *

import last_fm.views.analytics
import last_fm.views.dashboard
import last_fm.views.index
import last_fm.views.login
import last_fm.views.misc
import last_fm.views.usercp
ImageServer(app, os.path.join(app.static_folder, "artists"), allow_internet=True)
ImageServer(app, os.path.join(app.static_folder, "covers"), allow_internet=True)


@app.context_processor
def context_processor():
    context = {}

    context["now"] = datetime.now()
    context["timedelta"] = timedelta
    context["relativedelta"] = relativedelta

    if current_user.is_authenticated():
        context["current_user_has_gets"] = db.session.query(func.count(Get)).\
                                                      filter(Scrobble.user == current_user).\
                                                      scalar() > 0
        context["current_user_scrobble_count"] = db.session.query(func.count(Scrobble)).\
                                                            filter(Scrobble.user == current_user).\
                                                            scalar()

    return context


app.template_filter()(pluralize)
app.template_filter()(russian_strftime)


@app.after_request
def update_user_last_visit(response):
    if current_user.is_authenticated():
        current_user.last_visit = datetime.now()
        db.session.commit()
    return response
