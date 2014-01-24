# -*- coding: utf-8 -*-
from __future__ import absolute_import, unicode_literals

from collections import defaultdict
from datetime import datetime
from flask import *
import json
from sqlalchemy.orm import joinedload
from sqlalchemy.sql import distinct, func, literal_column, operators

from last_fm.app import app
from last_fm.db import db
from last_fm.models import *


@app.route("/conky/who-listened-to-this")
def who_listened_to_this():
    user__artist_scrobbles__last_scrobble = db.session.query(User.username,
                                                             func.count(Scrobble.id),
                                                             func.max(Scrobble.uts)).\
                                                       join(Scrobble.user).\
                                                       filter(Scrobble.artist == request.args["artist"],
                                                              Scrobble.user_id.in_([1, 3, 6, 7, 8, 9, 11])).\
                                                       group_by(Scrobble.user_id).\
                                                       order_by(User.username)
    user__track_scrobbles = defaultdict(lambda: 0, db.session.query(User.username, func.count(Scrobble.id)).\
                                                              join(Scrobble.user).\
                                                              filter(Scrobble.artist == request.args["artist"],
                                                                     Scrobble.track == request.args["track"]).\
                                                              group_by(Scrobble.user_id))
    user__artist_scrobbles__track_scrobbles = [(user,
                                                artist_scrobbles,
                                                user__track_scrobbles[user],
                                                datetime.fromtimestamp(last_scrobble).strftime("%d.%m.%Y"))
                                               for user, artist_scrobbles, last_scrobble in user__artist_scrobbles__last_scrobble]
    return ", ".join(["%s (%d, %d, %s)" % x for x in user__artist_scrobbles__track_scrobbles])
