# -*- coding=utf-8 -*-
from __future__ import absolute_import, division, unicode_literals

from collections import defaultdict
from datetime import timedelta
import itertools
import logging
from sqlalchemy.sql import func
import time
import twitter

from twitter_overkill.utils import join_list

from last_fm.celery import cron
from last_fm.constants import SIGNIFICANT_ARTIST_SCROBBLES
from last_fm.db import db
from last_fm.models import *
from last_fm.utils.model import update_scrobbles_for_user, get_artist
from last_fm.utils.twitter import get_api_for_user, post_tweet

logger = logging.getLogger(__name__)


@cron.job(minute="*/30")
def tweet_milestones():
    def get_artist_name(artist_id):
        return db.session.query(Artist).get(artist_id).name

    def get_artist_name2scrobbles(artist_id2scrobbles):
        return dict(map(lambda (artist_id, scrobbles): (get_artist_name(artist_id), scrobbles),
                        artist_id2scrobbles.iteritems()))

    chart_milestones_users = db.session.query(User).\
                                        filter(User.download_scrobbles == True,
                                               User.twitter_username != None,
                                               User.twitter_track_chart_milestones == True)
    artist_milestones_users = db.session.query(User).\
                                         filter(User.download_scrobbles == True,
                                                User.twitter_username != None,
                                                User.twitter_track_artist_milestones == True)
    artist_races_users = db.session.query(User).\
                                    filter(User.download_scrobbles == True,
                                           User.twitter_username != None,
                                           (User.twitter_win_artist_races == True) | (User.twitter_lose_artist_races == True))
    users = set(list(artist_milestones_users) + list(artist_races_users))

    for user in users:
        try:
            update_scrobbles_for_user(user)
        except Exception:
            return

    # common
    user2artist2scrobbles = {}
    for user in users:
        user2artist2scrobbles[user] = {}
        user2artist2scrobbles[user]["now"] = defaultdict(lambda: 0,
                                                         map(lambda (artist, scrobbles):
                                                                 (get_artist(artist).id, scrobbles),
                                                             db.session.query(Scrobble.artist, func.count(Scrobble.id)).\
                                                                        group_by(Scrobble.artist).\
                                                                        filter(Scrobble.user == user)))
        user2artist2scrobbles[user]["then"] = defaultdict(lambda: 0,
                                                          db.session.query(UserArtist.artist_id, UserArtist.scrobbles).\
                                                                     filter(UserArtist.user == user))

    for user in users:
        for artist_id, scrobbles in user2artist2scrobbles[user]["now"].iteritems():
            user_artist = db.session.query(UserArtist).\
                                     filter(UserArtist.user == user,
                                            UserArtist.artist_id == artist_id).\
                                     first()
            if user_artist is None:
                artist = get_artist_name(artist_id)
                user_artist = UserArtist()
                user_artist.user = user
                user_artist.artist_id = artist_id
                user_artist.first_scrobble = db.session.query(func.min(Scrobble.uts)).\
                                                        filter(Scrobble.user == user,
                                                               Scrobble.artist == artist).\
                                                        scalar()
                db.session.add(user_artist)
            user_artist.scrobbles = scrobbles

    twitter2user = {}
    for user in artist_races_users:
        twitter2user[user.twitter_data["id"]] = user

    # chart changes
    for user in chart_milestones_users:
        def get_chart(artist_id2scrobbles):
            artist2scrobbles = get_artist_name2scrobbles(artist_id2scrobbles)
            return sorted(artist2scrobbles.keys(), key=lambda artist: (-artist2scrobbles[artist], artist))[:20]

        chart_now = get_chart(user2artist2scrobbles[user]["now"])
        chart_then = get_chart(user2artist2scrobbles[user]["then"])

        chart_change_tweet_text = chart_change_tweet(chart_then, chart_now)
        if chart_change_tweet_text:
            post_tweet(user, chart_change_tweet_text)

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
                    track = db.session.query(Scrobble).\
                                       filter(Scrobble.user == user,
                                              Scrobble.artist == get_artist_name(artist_id)).\
                                       order_by(Scrobble.uts)\
                                       [milestone - 1]
                    milestones[artist_id] = (milestone, track.artist, track.track)

        for milestone, artist, track in milestones.values():
            post_tweet(user, "%d прослушиваний %s: %s!" % (milestone, artist, track.rstrip("!")))

    # races
    user2twitter_friends = {}
    def get_twitter_friends(user):
        if user in user2twitter_friends:
            return user2twitter_friends[user]

        try:
            user2twitter_friends[user] = get_api_for_user(user).GetFriendIDs(screen_name=user.twitter_username)
            return user2twitter_friends[user]
        except Exception:
            logger.debug("Unable to GetFriendIDs for %s", user.twitter_username, exc_info=True)
            return []
    for winner in artist_races_users:
        if winner.twitter_win_artist_races:
            for loser_twitter in get_twitter_friends(winner):
                if loser_twitter in twitter2user:
                    loser = twitter2user[loser_twitter]
                    # race
                    for artist_id in user2artist2scrobbles[winner]["now"]:
                        if user2artist2scrobbles[loser]["then"][artist_id] >= SIGNIFICANT_ARTIST_SCROBBLES and\
                           user2artist2scrobbles[winner]["then"][artist_id] < user2artist2scrobbles[loser]["then"][artist_id] and\
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
                    """
                    # slowpoke
                    for artist_id in user2artist2scrobbles[winner]["now"]:
                        artist = get_artist_name(artist_id)
                        if (user2artist2scrobbles[loser]["then"][artist_id] > 0 and
                                user2artist2scrobbles[loser]["then"][artist_id] < SIGNIFICANT_ARTIST_SCROBBLES and
                                user2artist2scrobbles[loser]["now"][artist_id] >= SIGNIFICANT_ARTIST_SCROBBLES and
                                (db.session.query(func.count(Scrobble.id)).
                                            filter(Scrobble.user == loser,
                                                   Scrobble.artist == artist,
                                                   Scrobble.uts > time.time() - timedelta(days=90).total_seconds()).
                                             scalar()
                                 /
                                 db.session.query(func.count(Scrobble.id)).
                                            filter(Scrobble.user == loser,
                                                   Scrobble.artist == artist,
                                                   Scrobble.uts > time.time() - timedelta(days=365).total_seconds()).
                                            scalar()

                                    >=

                                 90
                                 /
                                 365) and

                                user2artist2scrobbles[winner]["now"][artist_id] >= SIGNIFICANT_ARTIST_SCROBBLES and
                                (db.session.query(func.count(Scrobble.id)).
                                            filter(Scrobble.user == winner,
                                                   Scrobble.artist == artist,
                                                   Scrobble.uts < time.time() - timedelta(days=90).total_seconds()).
                                            scalar()
                                     >=
                                 SIGNIFICANT_ARTIST_SCROBBLES) and
                                (db.session.query(func.count(Scrobble.id)).
                                            filter(Scrobble.user == winner,
                                                   Scrobble.artist == artist).
                                            scalar()
                                     >=
                                 db.session.query(func.count(Scrobble.id)).
                                            filter(Scrobble.user_id.in_([u.id
                                                                         for u in db.session.query(User)
                                                                         if (u.twitter_data and
                                                                             u.twitter_data["id"] in get_twitter_friends(loser))]),
                                                   Scrobble.artist == artist).
                                            group_by(Scrobble.user_id).
                                            order_by(func.count(Scrobble.id).desc()).
                                            limit(1).
                                            scalar())):
                            if loser.twitter_lose_artist_races:
                                months = int((time.time() - db.session.query(UserArtist).
                                                                       filter(UserArtist.user == winner,
                                                                              UserArtist.artist_id == artist_id).
                                                                       one().first_scrobble) / (86400 * 30))
                                if months >= 12:
                                    if months >= 24:
                                        text = "%d лет" % (months / 12)
                                    else:
                                        text = "года"
                                else:
                                    text = "%d месяцев" % months

                                post_tweet(loser, "Вот @%s уже больше %s слушает %s, а до меня только сейчас дошло :(" % (
                                    winner.twitter_username,
                                    text,
                                    artist,
                                ))
                    """

    db.session.commit()


def chart_change_tweet(old, new):
    happened = []

    evictors = [n for n in new if n not in old]
    evicted = [o for o in old if o not in new]

    old_copy = list(old)
    new_copy = list(new)
    overtakers = []
    while True:
        for i, overtaker in enumerate(new_copy):
            if overtaker in old_copy:
                if i < old_copy.index(overtaker):
                    overtaken = []
                    for o in old_copy:
                        if o in new_copy:
                            if (old_copy.index(overtaker) > old_copy.index(o) and
                                    new_copy.index(overtaker) < new_copy.index(o)):
                                overtaken.append(o)
                        else:
                            for e in evicted:
                                if e not in overtaken:
                                    overtaken.append(e)
                    overtakers.append(([overtaker], overtaken))
                    old_copy.remove(overtaker)
                    new_copy.remove(overtaker)
                    break
        else:
            break
    while True:
        changed = False
        if len(overtakers) > 1:
            for i, (overtakers1, overtaken1) in enumerate(overtakers):
                for j, (overtakers2, overtaken2) in list(enumerate(overtakers))[i + 1:]:
                    if overtaken2 == overtaken1:
                        overtakers[i] = (overtakers1 + overtakers2, overtaken1)
                        del overtakers[j]
                        changed = True
                        break
                else:
                    continue
                break
        if not changed:
            break
    for overtaker, overtaken in overtakers:
        happened.append("%s обогнали %s" % (join_list(overtaker), join_list(overtaken)))

    if evictors and evicted:
        eviction = "%s вытеснили %s" % (join_list(evictors), join_list(evicted))
        first_evicted_position = old.index(evicted[0])
        last_evictor_position = new.index(evictors[-1])
        if last_evictor_position < first_evicted_position:
            eviction += ", обогнав %s" % join_list(new[last_evictor_position + 1:])
        happened.append(eviction)

    if happened:
        return "%s %s!" % ("У меня" if len(happened) > 1 else "А у меня", join_list(happened, ", ", ", а "))
