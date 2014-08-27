# -*- coding=utf-8 -*-
from __future__ import absolute_import, division, unicode_literals

from collections import defaultdict
import itertools
import logging
from sqlalchemy.sql import func
import twitter
import urllib2

from last_fm.celery import cron
from last_fm.db import db
from last_fm.models import *
from last_fm.utils.twitter import get_api_for_user, post_tweet

logger = logging.getLogger(__name__)


@cron.job(minute="*/30")
def tweet_milestones():
    session = db.create_scoped_session()

    mct = session.query(MilestoneCalculationTimestamp).first()

    def get_artist2scrobbles(user, min_count, max_uts=None):
        where = Scrobble.user == user
        if max_uts is not None:
            where = where & (Scrobble.uts <= max_uts)

        return defaultdict(lambda: 0,
                           session.query(func.lower(Scrobble.artist), func.count(Scrobble.id)).\
                                   group_by(Scrobble.artist).\
                                   filter(where).\
                                   having(func.count(Scrobble.id) >= min_count))

    artist_milestones_users = session.query(User).\
                                      filter(User.download_scrobbles == True,
                                             User.twitter_username != None,
                                             User.twitter_track_artist_milestones == True)
    artist_races_users = session.query(User).\
                                 filter(User.download_scrobbles == True,
                                        User.twitter_username != None,
                                        (User.twitter_win_artist_races == True) | (User.twitter_lose_artist_races == True))
    users = set(list(artist_milestones_users) + list(artist_races_users))

    for user in users:
        urllib2.urlopen("http://127.0.0.1:46400/update_scrobbles/%s" % user.username).read()

    # common
    user2artist2scrobbles = {}
    for user in users:
        user2artist2scrobbles[user] = {}
        user2artist2scrobbles[user]["now"] = get_artist2scrobbles(user, 250)
        user2artist2scrobbles[user]["then"] = get_artist2scrobbles(user, 250, mct.uts)

    twitter2user = {}
    for user in artist_races_users:
        twitter2user[user.twitter_data["id"]] = user

    # milestones
    for user in artist_milestones_users:
        artist2scrobbles_now = user2artist2scrobbles[user]["now"]
        artist2scrobbles_then = user2artist2scrobbles[user]["then"]

        milestones = {}
        for artist in artist2scrobbles_now:
            for milestone in itertools.chain([666], itertools.count(1000, 1000)):
                if artist2scrobbles_now[artist] < milestone:
                    break

                if artist2scrobbles_now[artist] >= milestone and artist2scrobbles_then[artist] < milestone:
                    track = session.query(Scrobble).\
                                    filter(Scrobble.user == user,
                                           Scrobble.artist == artist).\
                                    order_by(Scrobble.uts)\
                                    [milestone - 1]
                    milestones[artist] = (milestone, track.artist, track.track)

        for milestone, artist, track in milestones.values():
            post_tweet(user, "%d прослушиваний %s: %s!" % (milestone, artist, track.rstrip("!")))

    # races
    for winner in artist_races_users:
        if winner.twitter_win_artist_races:
            try:
                friends = get_api_for_user(winner).GetFriendIDs(screen_name=winner.twitter_username)
            except twitter.TwitterError:
                logger.exception("GetFriendIDs for %s", winner.twitter_username)
                continue

            for loser_twitter in friends:
                if loser_twitter in twitter2user:
                    loser = twitter2user[loser_twitter]
                    for artist in user2artist2scrobbles[winner]["now"]:
                        if user2artist2scrobbles[loser]["then"][artist] >= winner.twitter_artist_races_min_count and\
                           user2artist2scrobbles[winner]["then"][artist] <= user2artist2scrobbles[loser]["then"][artist] and\
                           user2artist2scrobbles[winner]["now"][artist] > user2artist2scrobbles[loser]["now"][artist]:
                            artist = session.query(Scrobble).filter(Scrobble.artist == artist).first().artist
                            post_tweet(winner, "Я обогнал @%s по количеству прослушиваний %s!" % (
                                loser.twitter_username,
                                artist.rstrip("!"),
                            ))
                            if loser.twitter_lose_artist_races:
                                post_tweet(loser, "А @%s обогнал меня по количеству прослушиваний %s :(" % (
                                    winner.twitter_username,
                                    artist,
                                ))

    mct.uts = session.query(func.max(Scrobble.uts)).scalar()
    session.commit()
