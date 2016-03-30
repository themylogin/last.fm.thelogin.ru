# -*- coding: utf-8 -*-
from __future__ import absolute_import, division, unicode_literals

from datetime import datetime
import dateutil.parser
from flask import *
import logging
from sqlalchemy.sql import func
import time

from last_fm.app import app
from last_fm.db import db
from last_fm.models import *

logger = logging.getLogger(__name__)


@app.route("/api/recommendations/")
def recommendations():
    return Response(stream_with_context(stream_recommendations()),
                    headers={b"X-Accel-Buffering": b"no"})


def stream_recommendations():
    include_users = [u[0] for u in db.session.query(User.id).\
                                        filter(User.username.in_(request.args.getlist("include-user")))]
    exclude_users = [u[0] for u in db.session.query(User.id).\
                                        filter(User.username.in_(request.args.getlist("exclude-user")))]
    datetime_start = request.args.get("datetime-start", datetime.min, type=dateutil.parser.parse)
    datetime_end = request.args.get("datetime-end", datetime.max, type=dateutil.parser.parse)
    min_scrobbles_count = request.args.get("min-scrobbles-count", 5, type=int)
    if request.args.get("sort") == "scrobbles-count":
        order_by = func.count(Scrobble.id).desc()
    else:
        order_by = func.rand()
    limit = request.args.get("limit", 1000, type=int)

    added = 0
    for artist, track in db.session.query(Scrobble.artist, Scrobble.track).\
                                    filter(
                                        Scrobble.user_id.in_(include_users),
                                        Scrobble.uts >= time.mktime(datetime_start.timetuple()),
                                        Scrobble.uts <= time.mktime(datetime_end.timetuple())
                                    ).\
                                    having(func.count(Scrobble.id) >= min_scrobbles_count).\
                                    group_by(Scrobble.artist, Scrobble.track).\
                                    order_by(order_by):
        if exclude_users:
            if db.session.query(func.count(Scrobble.id)).\
                          filter(
                              Scrobble.user_id.in_(exclude_users),
                              Scrobble.artist == artist,
                              Scrobble.track == track
                          ).\
                          scalar() > 0:
                continue

        yield json.dumps({"artist": artist, "track": track}) + b"\n"
        added += 1

        if added >= limit:
            break
