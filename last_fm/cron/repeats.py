# -*- coding: utf-8 -*-
from __future__ import absolute_import, division, unicode_literals

import itertools
import logging
import pytils
import urllib2
import time

from last_fm.celery import cron
from last_fm.db import db
from last_fm.models import *
from last_fm.utils.model import update_scrobbles_for_user
from last_fm.utils.twitter import post_tweet

logger = logging.getLogger(__name__)


@cron.job(minute="*/30")
def check_new_repeats():
    for user in db.session.query(User).\
                           filter(User.download_scrobbles == True,
                                  User.twitter_username != None,
                                  User.twitter_track_repeats == True):
        try:
            update_scrobbles_for_user(user)
        except Exception as e:
            logger.debug("Failed to update_scrobbles for %s", user.username, exc_info=True)
            continue

        db.session.commit()

        last_scrobble = db.session.query(Scrobble).\
                                   filter(Scrobble.user == user).\
                                   order_by(Scrobble.uts.desc()).\
                                   first()
        if last_scrobble is None:
            continue

        first_scrobble = last_scrobble
        scrobble_count = 1
        while True:
            prev_scrobble = db.session.query(Scrobble).\
                                       filter(Scrobble.user == user,
                                              Scrobble.uts < first_scrobble.uts).\
                                       order_by(Scrobble.uts.desc()).\
                                       first()
            if prev_scrobble and prev_scrobble.artist == first_scrobble.artist and prev_scrobble.track == first_scrobble.track:
                first_scrobble = prev_scrobble
                scrobble_count += 1
            else:
                break

        logger.debug("%s listened for %s - %s (id=%s) %d times", user.username,
                     first_scrobble.artist, first_scrobble.track,
                     first_scrobble.id, scrobble_count)
        if scrobble_count >= user.twitter_repeats_min_count:
            if (first_scrobble.artist, first_scrobble.track) not in [
                ("Magyar Posse", "[untitled]")
            ]:
                repeat = db.session.query(Repeat).\
                                    filter(Repeat.user == first_scrobble.user,
                                           Repeat.artist == first_scrobble.artist,
                                           Repeat.track == first_scrobble.track,
                                           Repeat.uts == first_scrobble.uts).\
                                    first()
                if repeat is None:
                    repeat = Repeat()
                    repeat.user = first_scrobble.user
                    repeat.artist = first_scrobble.artist
                    repeat.track = first_scrobble.track
                    repeat.uts = first_scrobble.uts
                    db.session.add(repeat)
                    db.session.commit()

                    if user.twitter_post_repeat_start:
                        post_tweet(user, "Слушаю на репите %s – %s" % (repeat.artist, repeat.track))

        db.session.commit()


@cron.job(minute="*/5")
def tweet_repeats():
    for repeat in db.session.query(Repeat).\
                             filter(Repeat.total == None):
        repeat = db.session.query(Repeat).get(repeat.id)

        try:
            update_scrobbles_for_user(repeat.user)
        except Exception as e:
            logger.debug("Failed to update_scrobbles for %s", repeat.user.username, exc_info=True)
            continue

        db.session.commit()

        is_this_track = lambda scrobble: scrobble.artist == repeat.artist and scrobble.track == repeat.track

        scrobbles = db.session.query(Scrobble).\
                               filter(Scrobble.user == repeat.user).\
                               order_by(Scrobble.uts.desc())\
                               [:500]

        if is_this_track(scrobbles[0]) and time.time() - scrobbles[0].uts < (scrobbles[1].uts - scrobbles[2].uts) * 5:
            continue

        repeat.total = 0
        for scrobble in itertools.dropwhile(lambda scrobble: not is_this_track(scrobble), scrobbles):
            if is_this_track(scrobble):
                repeat.total += 1
            else:
                break

        if repeat.total > 0 and repeat.user.twitter_username and repeat.user.twitter_track_repeats:
            db.session.commit()
            post_tweet(repeat.user, "Послушал на репите %s – %s %s" % (
                repeat.artist,
                repeat.track,
                pytils.numeral.get_plural(repeat.total, (u"раз", u"раза", u"раз"))
            ))
        else:
            db.session.delete(repeat)
            db.session.commit()
