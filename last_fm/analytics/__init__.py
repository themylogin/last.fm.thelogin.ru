# -*- coding=utf-8 -*-
from __future__ import absolute_import, division, unicode_literals

from collections import OrderedDict
from sqlalchemy.sql import func

from last_fm.db import db
from last_fm.models import *

__all__ = [b"find_day2scrobbles", b"find_day2scrobbles_gaps", b"find_first_scrobble_by_first_scrobble_appx",
           b"calculate_first_real_scrobble"]


def find_day2scrobbles(user, artist):
    day2scrobbles = OrderedDict([(day, 0)
                                 for day in range(int(db.session.query(func.min(Scrobble.uts)).\
                                                                 filter(Scrobble.user == user,
                                                                        Scrobble.artist == artist).\
                                                                 scalar() / 86400),
                                                  int(db.session.query(func.max(Scrobble.uts)).\
                                                                 filter(Scrobble.user == user,
                                                                        Scrobble.artist == artist).\
                                                                 scalar() / 86400) + 1)])
    for uts, in db.session.query(Scrobble.uts).\
                           filter(Scrobble.user == user,
                                  Scrobble.artist == artist):
        day2scrobbles[int(uts / 86400)] += 1

    for day in day2scrobbles:
        if day2scrobbles[day] < 4:
            day2scrobbles[day] = 0

    for day in day2scrobbles:
        if day2scrobbles[day] != 0:
            break
        del day2scrobbles[day]
    for day in reversed(day2scrobbles):
        if day2scrobbles[day] != 0:
            break
        del day2scrobbles[day]

    return day2scrobbles


def find_day2scrobbles_gaps(day2scrobbles):
    gaps = {}
    for day, scrobbles in day2scrobbles.iteritems():
        gaps[day + 1] = 0
        gap_day = day + 1
        while gap_day in day2scrobbles and day2scrobbles[gap_day] == 0:
            gaps[day + 1] += 1
            gap_day += 1

    return gaps


def find_first_scrobble_by_first_scrobble_appx(user, artist, first_scrobble_appx):
    return db.session.query(Scrobble).\
                      filter(Scrobble.user == user,
                             Scrobble.artist == artist,
                             Scrobble.uts >= first_scrobble_appx).\
                      order_by(Scrobble.uts).\
                      first()


def calculate_first_real_scrobble(user, artist):
    day2scrobbles = find_day2scrobbles(user, artist)
    gaps = find_day2scrobbles_gaps(day2scrobbles)

    total_scrobbles = sum(day2scrobbles.values())
    total_days = len(day2scrobbles)
    first_scrobble_appx = 0
    for gap_start, gap_length in sorted(gaps.items(), key=lambda (gap_start, gap_length): -gap_length):
        scrobbles_before_gap = sum([scrobbles for day, scrobbles in day2scrobbles.items() if day < gap_start])
        scrobbles_after_gap = sum([scrobbles for day, scrobbles in day2scrobbles.items() if day >= gap_start])
        if scrobbles_before_gap < scrobbles_after_gap:
            if scrobbles_before_gap / total_scrobbles < gap_length / total_days:
                first_scrobble_appx = (gap_start + gap_length) * 86400
            else:
                first_scrobble_appx = sorted(day2scrobbles.keys())[0] * 86400
            break

    return find_first_scrobble_by_first_scrobble_appx(user, artist, first_scrobble_appx - 5 * 86400)
