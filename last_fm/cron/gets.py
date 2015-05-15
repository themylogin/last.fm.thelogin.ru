# -*- coding=utf-8 -*-
from __future__ import absolute_import, division, unicode_literals

from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
import logging
import math
from pytils.numeral import get_plural
from sqlalchemy.sql import func, literal
import time

from last_fm.celery import cron
from last_fm.db import db
from last_fm.models import *
from last_fm.utils.network import get_network
from last_fm.utils.twitter import post_tweet

logger = logging.getLogger(__name__)


@cron.job(minute="*/5")
def tweet_gets():
    session = db.create_scoped_session()

    for user in session.query(User).\
                        filter(User.download_scrobbles == True,
                               User.twitter_username != None,
                               User.twitter_track_gets == True):
        for get in map(lambda x: x * 10000, range(1, int(session.query(func.count(Scrobble.id)).\
                                                                 filter(Scrobble.user == user).\
                                                                 scalar() / 10000) + 1)):
            if session.query(Get).\
                       filter(Get.user == user,
                              Get.get == get).\
                       first() is None:
                scrobble = session.query(Scrobble).\
                                   filter(Scrobble.user == user).\
                                   order_by(Scrobble.uts)\
                                   [get - 1]

                g = Get()
                g.user = user
                g.artist = scrobble.artist
                g.artist_image = get_network().get_artist(scrobble.artist).get_cover_image()
                g.track = scrobble.track
                g.datetime = scrobble.datetime
                g.get = get
                session.add(g)
                session.commit()

                post_tweet(user, "%d GET: %s – %s!" % (g.get, g.artist, g.track.rstrip("!")))
