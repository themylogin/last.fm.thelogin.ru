# -*- coding=utf-8 -*-
from __future__ import absolute_import, division, unicode_literals

from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
import logging
import math
from pytils.numeral import get_plural
from sqlalchemy.orm import aliased
from sqlalchemy.sql import func, literal
import time

from last_fm.celery import cron
from last_fm.db import db
from last_fm.models import *
from last_fm.utils.twitter import post_tweet

logger = logging.getLogger(__name__)


class AnniversaryBuilder(object):
    def query(self, now, user, max_possible_milestone):
        raise NotImplementedError

    def anniversary_for(self, user_artist, now_uts):
        raise NotImplementedError

    def anniversary_tweet(self, user_artist, anniversary):
        raise NotImplementedError


class PositiveAnniversaryBuilder(AnniversaryBuilder):
    def query(self, now, user, max_possible_milestone):
        anniversary_condition = literal(False)
        for anniversary in range(1, max_possible_milestone + 1):
            upper = now - relativedelta(years=anniversary)
            lower = upper - timedelta(days=1)
            anniversary_condition |= ((UserArtist.first_real_scrobble <= time.mktime(upper.timetuple())) &
                                      (UserArtist.first_real_scrobble >= time.mktime(lower.timetuple())))

        return [user_artist for user_artist in db.session.query(UserArtist).\
                                                          filter(UserArtist.user == user,
                                                                 UserArtist.scrobbles >= 250,
                                                                 anniversary_condition)
                if db.session.query(func.max(Scrobble.uts)).\
                              filter(Scrobble.user == user_artist.user,
                                     Scrobble.artist == user_artist.artist.name).\
                              scalar() > time.mktime((now - relativedelta(years=1)).timetuple())]

    def anniversary_for(self, user_artist, now_uts):
        return int(math.floor((now_uts - user_artist.first_real_scrobble) / (365 * 86400)))

    def anniversary_tweet(self, user_artist, anniversary):
        if anniversary == 1:
            text = "год"
        else:
            text = get_plural(anniversary, ("год", "года", "лет"))

        scrobble = db.session.query(Scrobble).\
                              filter(Scrobble.user == user_artist.user,
                                     Scrobble.artist == user_artist.artist.name,
                                     Scrobble.uts >= user_artist.first_real_scrobble).\
                              first()

        return "Уже %s слушаю %s: %s!" % (text, scrobble.artist, scrobble.track.rstrip("!"))


class NegativeAnniversaryBuilder(AnniversaryBuilder):
    def query(self, now, user, max_possible_milestone):
        scrobble_alias = aliased(Scrobble)
        anniversary_condition = literal(False)
        for anniversary in range(1, max_possible_milestone + 1):
            upper = now - relativedelta(years=anniversary)
            lower = upper - timedelta(days=1)
            anniversary_condition |= ((func.max(scrobble_alias.uts) <= time.mktime(upper.timetuple())) &
                                      (func.max(scrobble_alias.uts) >= time.mktime(lower.timetuple())))

        return [user_artist for user_artist in db.session.query(UserArtist).\
                                                          join(UserArtist.artist).\
                                                          join(scrobble_alias,
                                                               (scrobble_alias.user_id == UserArtist.user_id) &
                                                               (scrobble_alias.artist == Artist.name)).\
                                                          filter(UserArtist.user == user,
                                                                 UserArtist.scrobbles >= 250).\
                                                          having(anniversary_condition).\
                                                          group_by(UserArtist.id)]

    def anniversary_for(self, user_artist, now_uts):
        return int(math.floor((now_uts - db.session.query(func.max(Scrobble.uts)).
                                                    filter(Scrobble.user == user_artist.user,
                                                           Scrobble.artist == user_artist.artist.name).
                                                    scalar()) / (365 * 86400)))

    def anniversary_tweet(self, user_artist, anniversary):
        if anniversary == 1:
            text = "год не слушал"
        else:
            text = "%s не слушаю" % get_plural(anniversary, ("год", "года", "лет"))

        scrobble = db.session.query(Scrobble).\
                              filter(Scrobble.user == user_artist.user,
                                     Scrobble.artist == user_artist.artist.name).\
                              order_by(Scrobble.uts.desc()).\
                              first()

        return "Уже %s %s: %s :(" % (text, scrobble.artist, scrobble.track)


@cron.job(minute="*/5")
def tweet_anniversaries():
    now = datetime.now()
    now_uts = time.mktime(now.timetuple())
    builders = {True: PositiveAnniversaryBuilder(),
                False: NegativeAnniversaryBuilder()}

    for user in db.session.query(User).\
                           filter(User.download_scrobbles == True,
                                  User.twitter_username != None,
                                  User.twitter_track_artist_anniversaries == True):
        max_possible_milestone = int(math.floor((now_uts - db.session.query(func.min(Scrobble.uts)).
                                                                      filter(Scrobble.user == user).
                                                                      scalar()) / (365 * 86400)))

        for positive, builder in builders.iteritems():
            for user_artist in builder.query(now, user, max_possible_milestone):
                anniversary = builder.anniversary_for(user_artist, now_uts)
                if db.session.query(Anniversary).\
                              filter(Anniversary.user == user,
                                     Anniversary.artist == user_artist.artist,
                                     Anniversary.anniversary == anniversary,
                                     Anniversary.positive == positive).\
                              first() is None:
                    a = Anniversary()
                    a.user = user
                    a.artist = user_artist.artist
                    a.anniversary = anniversary
                    a.positive = positive
                    db.session.add(a)

                    post_tweet(user, builder.anniversary_tweet(user_artist, anniversary))

    db.session.commit()
