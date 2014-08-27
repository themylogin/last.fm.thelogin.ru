# -*- coding=utf-8 -*-
from __future__ import absolute_import, division, unicode_literals

from datetime import datetime, timedelta
from sqlalchemy.sql import func
import operator
import time

from themyutils.datetime.timedelta import timedelta_in_words
from twitter_overkill.utils import *

from last_fm.celery import cron
from last_fm.db import db
from last_fm.models import *
from last_fm.utils.twitter import post_tweet


def get_gender_verb(user, male, female):
    return female if user.data.get("gender") == "f" else male


@cron.job(month_of_year=1, day_of_month=1, hour=0, minute=0)
def tweet_year_stats():
    owner_id = 11

    year = datetime.now().year - 1
    year_start_uts = time.mktime(datetime(year=year, month=1, day=1).timetuple())
    year_end_uts = time.mktime(datetime(year=year, month=12, day=31, hour=23, minute=59, second=59).timetuple())

    tweets = []
    for user in db.session.query(User).\
                           filter(User.download_scrobbles == True,
                                  User.twitter_username != None):
        time_on_music = int(db.session.query(func.sum(ApproximateTrackLength.length)).\
                                       outerjoin((ApproximateTrackLength, Scrobble.approximate_track_length)).\
                                       filter(Scrobble.user == user,
                                              Scrobble.uts >= year_start_uts,
                                              Scrobble.uts <= year_end_uts).\
                                       scalar())

        time_on_new_music = int(db.session.query(func.sum(ApproximateTrackLength.length)).\
                                           outerjoin((ApproximateTrackLength, Scrobble.approximate_track_length)).\
                                           filter(Scrobble.user == user,
                                                  Scrobble.track.in_(map(operator.itemgetter(0),
                                                                         db.session.query(Scrobble.track).\
                                                                                    filter(Scrobble.user == user).\
                                                                                    group_by(Scrobble.track).\
                                                                                    having(func.min(Scrobble.uts) >= year_start_uts).\
                                                                                    all()))).\
                                           scalar())

        tweets.append((user, "В уходящем году я %s под музыку %s (%d%% времени), из них под новую — %s (%d%% музыки)" % (
            get_gender_verb(user, "провёл", "провела"),
            timedelta_in_words(time_on_music, 2),
            100 * time_on_music / (year_end_uts - year_start_uts),
            timedelta_in_words(time_on_new_music, 2),
            100 * time_on_new_music / time_on_music
        )))

        if user.id == owner_id:
            datetime_isStart = []
            for came, left in db.session.query(GuestVisit.came, GuestVisit.left).\
                                         filter(GuestVisit.left != None).\
                                         order_by(GuestVisit.came):
                datetime_isStart.append((came, True))
                datetime_isStart.append((left, False))

            smarthome_visits = []
            guests_in_house = 0
            last_party_start = None
            for dt, is_start in sorted(datetime_isStart, key=lambda t: t[0]):
                if is_start:
                    if guests_in_house == 0:
                        last_party_start = dt
                    guests_in_house += 1
                else:
                    guests_in_house -= 1
                    if guests_in_house <= 0:
                        guests_in_house = 0
                        smarthome_visits.append((last_party_start, dt))
        else:
            smarthome_visits = db.session.query(GuestVisit.came, GuestVisit.left).\
                                          filter(GuestVisit.user == user,
                                                 GuestVisit.left != None)

        time_in_smarthome = sum([left - came for came, left in smarthome_visits], timedelta())
        if time_in_smarthome:
            tweet = "В уходящем году я %s в умном доме %s" % (
                get_gender_verb(user, "провёл", "провела"),
                timedelta_in_words(time_in_smarthome, 2),
            )

            new_artists = []
            ignored_artists = []
            scrobble_in_smarthome = reduce(operator.or_, [(Scrobble.uts >= time.mktime(came.timetuple())) &\
                                                          (Scrobble.uts <= time.mktime(left.timetuple()))
                                                          for came, left in smarthome_visits])
            for artist, first_smarthome_scrobble_uts in db.session.query(Scrobble.artist, func.min(Scrobble.uts)).\
                                                                   filter(Scrobble.user == user,
                                                                          ~ Scrobble.artist.in_(["Kokomo", "Laura"]),
                                                                          scrobble_in_smarthome).\
                                                                   group_by(Scrobble.artist):
                scrobbles_before_first_smarthome_scrobble = db.session.query(func.count(Scrobble)).\
                                                                       filter(Scrobble.user == user,
                                                                              Scrobble.artist == artist,
                                                                              Scrobble.uts < first_smarthome_scrobble_uts).\
                                                                       scalar()
                scrobbles_in_smarthome = db.session.query(func.count(Scrobble)).\
                                                    filter(Scrobble.user == user,
                                                           Scrobble.artist == artist,
                                                           scrobble_in_smarthome).\
                                                    scalar()
                scrobbles_after_first_smarthome_scrobble_not_in_smarthome = db.session.query(func.count(Scrobble)).\
                                                                                       filter(Scrobble.user == user,
                                                                                              Scrobble.artist == artist,
                                                                                              Scrobble.uts >= first_smarthome_scrobble_uts,
                                                                                              ~ scrobble_in_smarthome).\
                                                                                       scalar()
                if scrobbles_before_first_smarthome_scrobble < 10:
                    if scrobbles_after_first_smarthome_scrobble_not_in_smarthome >= 10:
                        if scrobbles_before_first_smarthome_scrobble / scrobbles_after_first_smarthome_scrobble_not_in_smarthome < 0.1:
                            new_artists.append((artist, scrobbles_after_first_smarthome_scrobble_not_in_smarthome))

                    if scrobbles_in_smarthome >= 10 and scrobbles_after_first_smarthome_scrobble_not_in_smarthome < 10:
                        ignored_artists.append((artist, scrobbles_in_smarthome))

            new_artists = map(operator.itemgetter(0), sorted(new_artists, key=lambda (a, s): -s))
            ignored_artists = map(operator.itemgetter(0), sorted(ignored_artists, key=lambda (a, s): -s))

            tweets.append((user, tweet_with_list(tweet, tweet + ", узнав про %s", new_artists)))
            tweets.append((user, tweet_with_list(None, "Не понравились %s", ignored_artists)))

    me = db.session.query(User).get(owner_id)
    post_tweet(me, "Всех с новым годом! А особенно вот этих котиков:", False)
    for user, tweet in tweets:
        post_tweet(user, tweet)
