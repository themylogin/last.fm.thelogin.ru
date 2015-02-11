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
from last_fm.utils.twitter import post_tweet

logger = logging.getLogger(__name__)


@cron.job(minute="*/5")
def tweet_anniversaries():
    session = db.create_scoped_session()
    now = datetime.now()
    now_uts = time.mktime(now.timetuple())

    for user in session.query(User).\
                        filter(User.download_scrobbles == True,
                               User.twitter_username != None,
                               User.twitter_track_artist_anniversaries == True):
        max_possible_milestone = int(math.floor((now_uts - session.query(func.min(Scrobble.uts)).\
                                                                   filter(Scrobble.user == user).\
                                                                   scalar()) / (365 * 86400)))

        milestone_condition = literal(False)
        for anniversary in range(1, max_possible_milestone + 1):
            upper = datetime.now() - relativedelta(years=anniversary)
            lower = upper - timedelta(days=1)
            milestone_condition |= ((UserArtist.first_real_scrobble <= time.mktime(upper.timetuple())) &
                                    (UserArtist.first_real_scrobble >= time.mktime(lower.timetuple())))

        for user_artist in session.query(UserArtist).\
                                   filter(UserArtist.user == user,
                                          milestone_condition):
            anniversary = int(math.floor((now_uts - user_artist.first_real_scrobble) / (365 * 86400)))
            if session.query(Anniversary).\
                       filter(Anniversary.user == user,
                              Anniversary.artist == user_artist.artist,
                              Anniversary.anniversary == anniversary).\
                       first() is None:
                a = Anniversary()
                a.user = user
                a.artist = user_artist.artist
                a.anniversary = anniversary
                session.add(a)

                if db.session.query(func.max(Scrobble.uts)).\
                              filter(Scrobble.user == user, Scrobble.artist == user_artist.artist.name).\
                              scalar() < time.time() - user.artist_expires_years * 365 * 86400:
                    continue

                if anniversary == 1:
                    text = "год"
                else:
                    text = get_plural(anniversary, ("год", "года", "лет"))

                scrobble = session.query(Scrobble).\
                                   filter(Scrobble.user == user,
                                          Scrobble.artist == user_artist.artist.name,
                                          Scrobble.uts >= user_artist.first_real_scrobble).\
                                   first()

                post_tweet(user, "Уже %s слушаю %s: %s!" % (text, scrobble.artist, scrobble.track.rstrip("!")))

    session.commit()
