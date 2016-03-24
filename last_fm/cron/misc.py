# -*- coding=utf-8 -*-
from __future__ import absolute_import, division, unicode_literals

from collections import defaultdict, OrderedDict
from datetime import datetime, timedelta
import itertools
import logging
import mpd
from sqlalchemy.sql import func, literal_column
import time

from last_fm.analytics import calculate_first_real_scrobble
from last_fm.celery import cron
from last_fm.db import db
from last_fm.models import *
from last_fm.utils.mpd import get_mpd
from last_fm.utils.string import streq

logger = logging.getLogger(__name__)
    

@cron.job(hour=5, minute=0)
def calculate_approximate_track_lengths():
    client = get_mpd()

    db.session.execute("""
        DELETE FROM approximate_track_length
        WHERE real_length IS NULL AND last_update < (
            SELECT FROM_UNIXTIME(MAX(uts))
            FROM scrobble
            WHERE scrobble.artist = approximate_track_length.artist AND
                  scrobble.track = approximate_track_length.track
        )
    """)

    cheaters_ids = [user.id for user in db.session.query(User).filter(User.cheater == True)]
    for artist, track in db.session.query(Scrobble.artist, Scrobble.track).\
                                    outerjoin((ApproximateTrackLength,
                                                  ((ApproximateTrackLength.artist == Scrobble.artist) &
                                                   (ApproximateTrackLength.track == Scrobble.track)))).\
                                    filter(~Scrobble.user_id.in_(cheaters_ids),
                                           ApproximateTrackLength.track == None).\
                                    group_by(Scrobble.artist, Scrobble.track):
        lengths = defaultdict(lambda: 0)
        prev_tracks_lengths = defaultdict(lambda: defaultdict(lambda: 0))
        next_tracks_lengths = defaultdict(lambda: defaultdict(lambda: 0))
        get_prev_scrobble = lambda scrobble: db.session.query(Scrobble).\
                                                        filter(Scrobble.user == scrobble.user,
                                                               Scrobble.uts < scrobble.uts).\
                                                        order_by(Scrobble.uts.desc()).\
                                                        first()
        get_next_scrobble = lambda scrobble: db.session.query(Scrobble).\
                                                        filter(Scrobble.user == scrobble.user,
                                                               Scrobble.uts > scrobble.uts).\
                                                        order_by(Scrobble.uts.asc()).\
                                                        first()
        for scrobble in db.session.query(Scrobble).\
                                   filter(~Scrobble.user_id.in_(cheaters_ids),
                                          Scrobble.artist == artist,
                                          Scrobble.track == track):
            prev_scrobble = get_prev_scrobble(scrobble)
            if prev_scrobble:
                lengths[scrobble.uts - prev_scrobble.uts] += 1

                prev_prev_scrobble = get_prev_scrobble(prev_scrobble)
                if prev_prev_scrobble:
                    prev_tracks_lengths[prev_scrobble.name][prev_scrobble.uts - prev_prev_scrobble.uts] += 1
                    prev_tracks_lengths[prev_scrobble.name][scrobble.uts - prev_scrobble.uts] += 1

            next_scrobble = get_next_scrobble(scrobble)
            if next_scrobble:
                lengths[next_scrobble.uts - scrobble.uts] += 1

                next_next_scrobble = get_next_scrobble(next_scrobble)
                if next_next_scrobble:
                    next_tracks_lengths[next_scrobble.name][next_scrobble.uts - scrobble.uts] += 1
                    next_tracks_lengths[next_scrobble.name][next_next_scrobble.uts - next_scrobble.uts] += 1

        if lengths:
            get_top_track_lengths = lambda tracks_lengths: (sorted(tracks_lengths.items(),
                                                                   key=lambda (track, lengths):
                                                                           -sum(lengths.values()))[0][1]
                                                            if tracks_lengths
                                                            else {})

            def get_intervals(lengths):
                intervals = {}
                for length, occurances in sorted(lengths.items(), key=lambda item: -item[1]):
                    found = False
                    for interval in intervals:
                        if abs(interval - length) < 10:
                            intervals[interval] += [length] * occurances
                            found = True
                            break
                    if not found:
                        intervals[length] = [length]

                return OrderedDict(sorted(intervals.items(), key=lambda (k, v): -len(v))[:3])

            prev_intervals = get_intervals(get_top_track_lengths(prev_tracks_lengths))
            this_intervals = get_intervals(lengths)
            next_intervals = get_intervals(get_top_track_lengths(next_tracks_lengths))

            lengths = []
            #
            intervals = filter(None, [prev_intervals, this_intervals, next_intervals])
            for combination_length in range(len(intervals), 1, -1):
                for combination in itertools.combinations(intervals, combination_length):
                    lengths_by_indexes = lambda combination, indexes: sum(map(lambda (interval, index): interval[index],
                                                                              zip(combination, indexes)), [])
                    deviation = lambda lengths: sum([abs(length - (sum(lengths) / len(lengths))) for length in lengths])
                    def cmp(lengths1, lengths2):
                        if deviation(lengths1) < 10 and deviation(lengths2) > 10:
                            return -1
                        if deviation(lengths1) > 10 and deviation(lengths2) < 10:
                            return 1

                        c1 = len(lengths_by_indexes(combination, lengths1))
                        c2 = len(lengths_by_indexes(combination, lengths2))
                        if c1 > c2:
                            return -1
                        elif c1 < c2:
                            return 1
                        else:
                            return 0

                    indexes = sorted(itertools.product(*map(lambda col: col.keys(), combination)), key=deviation)[0]
                    if deviation(indexes) < 10: # and len(lengths_by_indexes(combination, indexes)) > sum(map(lambda x: len(sum(x.values(), [])), combination)) * 0.3:
                        lengths = lengths_by_indexes(combination, indexes)
                        #print "FOUND"
                        #print indexes
                        #print combination
                        break
                if lengths:
                    break
            if not lengths:
                lengths = this_intervals.values()[0]
                #print "FALLING BACK"

            length = sum(lengths) / len(lengths)
            stat_length = length
            real_length = None

            try:
                result = list(client.search("title", track.encode("utf-8")))
            except mpd.MPDError:
                logger.warning("MPD Error", exc_info=True)
                client = get_mpd()
            else:
                for tr in result:
                    if "artist" not in tr:
                        continue
                    if isinstance(tr["artist"], list):
                        tr["artist"] = tr["artist"][0]

                    if "title" not in tr:
                        continue
                    if isinstance(tr["title"], list):
                        tr["title"] = tr["title"][0]

                    if streq(artist, tr["artist"].decode("utf-8")) and streq(track, tr["title"].decode("utf-8")):
                        real_length = int(tr["time"])
                        length = real_length

                        if abs(real_length - length) > 10:
                            logger.debug("Length for %s - %s is %02d:%02d does not match real %02d:%02d", artist, track,
                                         length / 60, length % 60, real_length / 60, real_length % 60)
                            #print prev_intervals.keys()
                            #print this_intervals.keys()
                            #print next_intervals.keys()
                        else:
                            logger.debug("Length for %s - %s is %02d:%02d matches real %02d:%02d", artist, track,
                                         length / 60, length % 60, real_length / 60, real_length % 60)
                        break

            db.session.execute(ApproximateTrackLength.__table__.insert().values(
                artist      = artist,
                track       = track,
                length      = length,
                stat_length = stat_length,
                real_length = real_length,
                last_update = datetime.now(),
            ))
            db.session.commit()


@cron.job(day_of_month=1, hour=6, minute=0)
def calculate_coincidences():
    db.session.execute("DELETE FROM `" + Coincidence.__tablename__ + "`")

    step = 1e7
    for i in xrange(*db.session.query(func.min(Scrobble.uts),
                                      func.max(Scrobble.uts),
                                      literal_column(str(step))).first()):
        db.session.execute("""
            INSERT INTO `""" + Coincidence.__tablename__ + """` (artist, track, users_uts)
            SELECT
                first_scrobble.artist,
                first_scrobble.track,
                CONCAT(
                    CONCAT_WS(":", first_scrobble.user_id, first_scrobble.uts),
                    ";",
                    GROUP_CONCAT(
                        CONCAT_WS(":", succeeding_scrobbles.user_id, succeeding_scrobbles.uts)
                        SEPARATOR ";"
                    )
                )
            FROM `""" + Scrobble.__tablename__ + """` first_scrobble
            INNER JOIN `""" + Scrobble.__tablename__ + """` succeeding_scrobbles ON (
                succeeding_scrobbles.user_id != first_scrobble.user_id AND
                succeeding_scrobbles.artist = first_scrobble.artist AND
                succeeding_scrobbles.track = first_scrobble.track AND
                (
                    (succeeding_scrobbles.uts = first_scrobble.uts AND succeeding_scrobbles.id > first_scrobble.id) OR
                    (succeeding_scrobbles.uts BETWEEN first_scrobble.uts + 1 AND first_scrobble.uts + 300)
                )
            )
            LEFT JOIN `""" + Scrobble.__tablename__ + """` preceding_scrobbles ON (
                preceding_scrobbles.user_id != first_scrobble.user_id AND
                preceding_scrobbles.artist = first_scrobble.artist AND
                preceding_scrobbles.track = first_scrobble.track AND
                (
                    (preceding_scrobbles.uts = first_scrobble.uts AND preceding_scrobbles.id < first_scrobble.id) OR
                    (preceding_scrobbles.uts BETWEEN first_scrobble.uts - 300 AND first_scrobble.uts - 1)
                )
            )
            WHERE first_scrobble.uts BETWEEN :min AND :max
            GROUP BY first_scrobble.id
            HAVING COUNT(preceding_scrobbles.id) = 0
            ORDER BY first_scrobble.uts
        """, {"min" : i, "max" : i + step - 1})

    db.session.execute("COMMIT")


@cron.job(minute="*/5")
def calculate_first_real_scrobbles():
    for user_artist in db.session.query(UserArtist).\
                                  filter(UserArtist.first_scrobble <= time.time() - 360 * 86400,
                                         UserArtist.first_real_scrobble == None):
        user_artist.first_real_scrobble = calculate_first_real_scrobble(user_artist.user,
                                                                        user_artist.artist.name).uts

    db.session.commit()
