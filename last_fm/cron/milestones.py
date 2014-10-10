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


"""
def post_tweet(user, text):
    print user.username, text
"""


@cron.job(minute="*/30")
def tweet_milestones():
    session = db.create_scoped_session()

    def get_artist_id(artist_name):
        artist = session.query(Artist).filter(Artist.name == artist_name).first()
        if artist is None:
            artist = Artist()
            artist.name = artist_name
            session.add(artist)
            session.commit()
        return artist.id

    def get_artist_name(artist_id):
        return session.query(Artist).get(artist_id).name

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
        user2artist2scrobbles[user]["now"] = defaultdict(lambda: 0,
                                                         map(lambda (artist, scrobbles):
                                                                 (get_artist_id(artist), scrobbles),
                                                             session.query(Scrobble.artist, func.count(Scrobble.id)).\
                                                                     group_by(Scrobble.artist).\
                                                                     filter(Scrobble.user == user).\
                                                                     having(func.count(Scrobble.id) >= 250)))
        user2artist2scrobbles[user]["then"] = defaultdict(lambda: 0,
                                                          session.query(UserArtist.artist_id, UserArtist.scrobbles).\
                                                                  filter(UserArtist.user == user,
                                                                         UserArtist.scrobbles >= 250))

    for user in users:
        for artist_id, scrobbles in user2artist2scrobbles[user]["now"].iteritems():
            user_artist = session.query(UserArtist).\
                                  filter(UserArtist.user == user,
                                         UserArtist.artist_id == artist_id).\
                                  first()
            if user_artist is None:
                artist = get_artist_name(artist_id)
                user_artist = UserArtist()
                user_artist.user = user
                user_artist.artist_id = artist_id
                user_artist.first_scrobble = session.query(func.min(Scrobble.uts)).\
                                                     filter(Scrobble.user == user,
                                                            Scrobble.artist == artist).\
                                                     scalar()
                session.add(user_artist)
            user_artist.scrobbles = scrobbles

    twitter2user = {}
    for user in artist_races_users:
        twitter2user[user.twitter_data["id"]] = user

    # milestones
    for user in artist_milestones_users:
        artist2scrobbles_now = user2artist2scrobbles[user]["now"]
        artist2scrobbles_then = user2artist2scrobbles[user]["then"]

        milestones = {}
        for artist_id in artist2scrobbles_now:
            for milestone in itertools.chain([666], itertools.count(1000, 1000)):
                if artist2scrobbles_now[artist_id] < milestone:
                    break

                if artist2scrobbles_now[artist_id] >= milestone and artist2scrobbles_then[artist_id] < milestone:
                    track = session.query(Scrobble).\
                                    filter(Scrobble.user == user,
                                           Scrobble.artist == get_artist_name(artist_id)).\
                                    order_by(Scrobble.uts)\
                                    [milestone - 1]
                    milestones[artist_id] = (milestone, track.artist, track.track)

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
                    for artist_id in user2artist2scrobbles[winner]["now"]:
                        if user2artist2scrobbles[loser]["then"][artist_id] >= winner.twitter_artist_races_min_count and\
                           user2artist2scrobbles[winner]["then"][artist_id] <= user2artist2scrobbles[loser]["then"][artist_id] and\
                           user2artist2scrobbles[winner]["now"][artist_id] > user2artist2scrobbles[loser]["now"][artist_id]:
                            artist = get_artist_name(artist_id)
                            post_tweet(winner, "Я обогнал @%s по количеству прослушиваний %s!" % (
                                loser.twitter_username,
                                artist.rstrip("!"),
                            ))
                            if loser.twitter_lose_artist_races:
                                post_tweet(loser, "А @%s обогнал меня по количеству прослушиваний %s :(" % (
                                    winner.twitter_username,
                                    artist,
                                ))

    session.commit()
