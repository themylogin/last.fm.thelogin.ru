# -*- coding: utf-8 -*-
from __future__ import absolute_import, division, unicode_literals

from collections import defaultdict
from datetime import date, datetime, timedelta
import dateutil.parser
from flask import *
import json
import itertools
import math
import numpy
import operator
import pytils
from sqlalchemy.orm import joinedload
from sqlalchemy.sql import distinct, func, literal_column, operators
import time

from themyutils.datetime.timedelta import timedelta_in_words
from themyutils.itertools import unique_items

from last_fm.app import app
from last_fm.cache import cache
from last_fm.db import db
from last_fm.models import *


def cached_analytics_view(view):
    def decorated():
        cache_key = request.url

        result = cache.get(cache_key)
        if app.debug or result is None:
            result = view()
            cache.set(cache_key, result, timeout=3600)

        return render_template("analytics/%s.html" % view.__name__[len("analytics_"):], **result)

    decorated.__name__ = view.__name__
    return decorated


def get_user2artist2scrobbles(user_ids, min_scrobbles=0):
    return {user_id: dict(db.session.query(Scrobble.artist, func.count(Scrobble.id)).\
                                     group_by(Scrobble.artist).\
                                     filter_by(user_id=user_id).\
                                     having(func.count(Scrobble.id) >= (min_scrobbles(user_id)
                                                                        if callable(min_scrobbles)
                                                                        else min_scrobbles)))
            for user_id in user_ids}


def get_user2artistlower2scrobbles(user2artist2scrobbles):
    return {user: {artist.lower(): scrobbles
                   for artist, scrobbles in user2artist2scrobbles[user].items()}
            for user in user2artist2scrobbles.keys()}


def get_user2username():
    return dict(db.session.query(User.id, User.username).all())


@app.route("/analytics")
def analytics():
    return render_template("analytics/index.html", users=db.session.query(User).filter(User.download_scrobbles==True).order_by(User.username))


@app.route("/analytics/fight")
@cached_analytics_view
def analytics_fight():
    user_ids = map(int, request.args.getlist("users"))

    user2artist2first_scrobble = dict([
        (user_id, dict([
            (artist, db.session.query(Scrobble).\
                                filter(Scrobble.user_id == user_id,
                                       Scrobble.artist == artist).\
                                order_by(Scrobble.uts).\
                                first())
            for artist, scrobble_count in db.session.query(Scrobble.artist,
                                                           func.count(Scrobble.id)).\
                                                     filter(Scrobble.user_id == user_id).\
                                                     group_by(Scrobble.artist)
            if scrobble_count > int(request.args["more_than_x_scrobbles"])
        ]))
        for user_id in user_ids
    ])

    table_body = [
        (artist, [
            (user2artist2first_scrobble[user1][artist], user2artist2first_scrobble[user1][artist].uts == min([
                user2artist2first_scrobble[user2][artist].uts
                for user2 in user_ids
            ]))
            for user1 in user_ids
        ])
        for artist in set.intersection(*[set(artist2first_scrobble.keys()) for artist2first_scrobble in user2artist2first_scrobble.values()])
    ]
    table_header = [
        (db.session.query(User).get(user_id), len([
            row
            for row in table_body
            if row[1][user_ids.index(user_id)][1]
        ]))
        for user_id in user_ids
    ]

    if request.args.get("sort") == "date":
        table_body.sort(key=lambda row: max([scrobble.uts for (scrobble, is_winner) in row[1]]))
    if request.args.get("sort") == "title":
        table_body.sort(key=lambda row: row[0].lower())
    if request.args.get("sort") == "s_mordvinov":
        table_body.sort(key=lambda row: row[0].lower())
        table_body.sort(key=lambda row: map(operator.itemgetter(1), row[1]).index(True))

    return dict(table_header=table_header, table_body=table_body)


@app.route("/analytics/repeat")
@cached_analytics_view
def analytics_repeat():
    user = db.session.query(User).get(request.args.get("user"))

    repeat_sessions = []
    if request.args.has_key("seq"):
        scrobbles = [(scrobble.artist + " – " + scrobble.track, scrobble) for scrobble in db.session.query(Scrobble).filter_by(user=user).order_by(Scrobble.uts)]

        i = 0
        while i < len(scrobbles):
            for l in xrange(1, 16):
                repeat_session_length = 1;
                while True:
                    ok = True
                    for j in xrange(0, l):
                        if not (i + j < len(scrobbles) and i + repeat_session_length * l + j < len(scrobbles) and scrobbles[i + j][0] == scrobbles[i + repeat_session_length * l + j][0]):
                            ok = False
                    if ok:
                        repeat_session_length += 1
                    else:
                        break
                if repeat_session_length >= 2 and l * repeat_session_length >= int(request.args.get("more_than_x_scrobbles")):
                    repeat_sessions.append({
                        "track"     : "<br />".join([scrobble[0] for scrobble in scrobbles[i:i+l]]),
                        "scrobbles" : repeat_session_length,
                        "start"     : datetime.fromtimestamp(scrobbles[i][1].uts),
                        "end"       : datetime.fromtimestamp(scrobbles[i + repeat_session_length * l - 1][1].uts)
                    })

                    i += repeat_session_length * l - 1
                    break
            i += 1
    else:
        previous_track = None
        previous_track_scrobbles = 0
        previous_track_start = 0
        previous_track_end = 0
        for scrobble in db.session.query(Scrobble).filter_by(user=user).order_by(Scrobble.uts):
            track = scrobble.artist + " – " + scrobble.track
            if track == previous_track:
                previous_track_scrobbles += 1
                previous_track_end = scrobble.uts
            else:
                if previous_track_scrobbles >= int(request.args.get("more_than_x_scrobbles")):
                    repeat_sessions.append({
                        "track"     : previous_track,
                        "scrobbles" : previous_track_scrobbles,
                        "start"     : datetime.fromtimestamp(previous_track_start),
                        "end"       : datetime.fromtimestamp(previous_track_end),
                    })

                previous_track = track
                previous_track_scrobbles = 1
                previous_track_start = scrobble.uts

    return dict(user=user, repeat_sessions=repeat_sessions)


@app.route("/analytics/jump_to_date")
def analytics_jump_to_date():
    return redirect("http://www.lastfm.ru/user/%(user)s/tracks?page=%(page)d" % {
        "user"  : db.session.query(User).get(request.args["user"]).username,
        "page"  : math.ceil(db.session.query(func.count(Scrobble.id)).filter(
            Scrobble.user_id == request.args["user"],
            Scrobble.uts > time.mktime(dateutil.parser.parse(request.args["date"], dayfirst=True).timetuple())
        ).scalar() / 50.0) + 1
    })


@app.route("/analytics/recommendations")
@cached_analytics_view
def analytics_recommendations():
    user = db.session.query(User).get(request.args.get("user"))

    table_header = ["Исполнитель", "Друзья", "Друзей", "Прослушиваний"]
    table_body = db.session.query(
        func.concat('<a href="http://last.fm/music/', Scrobble.artist, '">', Scrobble.artist, '</a>'),
        func.group_concat(distinct(User.username).op("SEPARATOR")(literal_column('", "'))),
        func.count(distinct(User.username)),
        func.count(Scrobble.id)
    ).\
    join(User).\
    filter(
        Scrobble.user_id.in_(request.args.getlist("users")),
        ~Scrobble.artist.in_([a[0] for a in db.session.query(distinct(Scrobble.artist)).filter_by(user=user).all()])
    ).\
    group_by(Scrobble.artist).\
    order_by(-func.count(Scrobble.id) if request.args.get("target") == "scrobbles" else -func.count(distinct(User.username))).\
    all()[0:1000]

    return dict(title="Рекомендации для %s" % user.username, table_header=table_header, table_body=table_body)


@app.route("/analytics/compability")
@cached_analytics_view
def analytics_compability():
    user2set = dict([
        (user_id, map(operator.itemgetter(0), {
            "artist"            : db.session.query(Scrobble.artist).\
                                             group_by(Scrobble.artist),
            "track"             : db.session.query(func.concat(Scrobble.artist, literal_column('" – "'), Scrobble.track)).\
                                             group_by(Scrobble.artist, Scrobble.track),
        }
        [request.args.get("criterion")].\
        filter_by(user_id=user_id).\
        having(func.count(Scrobble.id) > int(request.args.get("more_than_x_scrobbles"))).\
        all()))
        for user_id in map(int, request.args.getlist("users"))
    ])

    user2username = get_user2username()
    
    length2groups = [
        (length, filter(lambda (users, set): len(set) > 0, sorted([
            (
                ", ".join(sorted([user2username[i] for i in user2username if i in group], key=lambda username: username.lower())),
                reduce(set.intersection, map(set, [user2set[user_id] for user_id in group]))
            )
            for group in itertools.combinations(map(int, request.args.getlist("users")), length) if len(group) == length
        ], key=lambda (users, set): -len(set)))[:10])
        for length in range(2, len(user2username) + 1)
    ]

    return dict(length2groups=length2groups)


@app.route("/analytics/the_only_ones")
@cached_analytics_view
def analytics_the_only_ones():
    us = request.args.getlist("us", type=int)
    them = request.args.getlist("them", type=int)
    more_than_x_scrobbles_us = request.args.get("more_than_x_scrobbles_us", type=int)
    more_than_x_scrobbles_them = request.args.get("more_than_x_scrobbles_them", type=int)
    user2artist2scrobbles = get_user2artist2scrobbles(us + them,
                                                      lambda user: (more_than_x_scrobbles_us if user in us
                                                                    else more_than_x_scrobbles_them))
    user2artistlower2scrobbles = get_user2artistlower2scrobbles(user2artist2scrobbles)
    
    user2username = get_user2username()
    userids_sorted = sorted(us, key=lambda id: user2username[id])

    table_header = [user2username[id] for id in userids_sorted]
    table_body = sorted([
        (artist, [user2artistlower2scrobbles[user][artist.lower()] for user in userids_sorted])
        for artist in set.union(*map(set, [artist2scrobbles.keys()
                                           for artist2scrobbles in user2artist2scrobbles.values()]))
        if reduce(operator.and_, [artist.lower() in user2artistlower2scrobbles[user].keys() if user in us
                                  else artist.lower() not in user2artistlower2scrobbles[user].keys()
                                  for user in user2artist2scrobbles.keys()])
    ], key=lambda t: -sum(t[1]))

    return dict(title="Музыка, которую %(word)s только %(users)s" % {
                    "word"   : "слушают" if len(table_header) > 1 else "слушает",
                    "users"  : ", ".join(table_header)
                },
                table_header=table_header,
                table_body=table_body)


@app.route("/analytics/closer")
@cached_analytics_view
def analytics_closer():
    user1 = db.session.query(User).get(int(request.args.get("user1")))
    user2 = db.session.query(User).get(int(request.args.get("user2")))

    if request.args.get("criterion") == "artist":
        field = Scrobble.artist
    if request.args.get("criterion") == "track":
        field = func.concat(Scrobble.artist, Scrobble.track)

    start_uts = max(
        db.session.query(func.min(Scrobble.uts)).filter_by(user=user1),
        db.session.query(func.min(Scrobble.uts)).filter_by(user=user2)
    )

    def gather_shares(user):
        data = {}
        for (share, uts) in db.session.query(field, Scrobble.uts).filter(Scrobble.user == user, Scrobble.uts >= start_uts):
            week = int(math.floor(uts / (86400 * 7)) * (86400 * 7))
            if week not in data:
                data[week] = set()
            if share not in data[week]:
                data[week].add(share)
        return data
    user1_shares = gather_shares(user1)
    user2_shares = gather_shares(user2)

    if request.args.get("criterion_type") == "integral":
        def integrate_shares(shares):
            prev_week = None
            for week in sorted(shares.keys()):
                if prev_week:
                    shares[week] = set.union(shares[week], shares[prev_week])
                prev_week = week
            return shares
        user1_shares = integrate_shares(user1_shares)
        user2_shares = integrate_shares(user2_shares)

    data = [
        [
            date.fromtimestamp(week).strftime("%b %Y"),
            len(user1_shares[week] - user2_shares[week]) / float(len(user1_shares[week])),
            "",
            ", ".join(sorted(user1_shares[week] - user2_shares[week])),
           -len(user2_shares[week] - user1_shares[week]) / float(len(user2_shares[week])),
            "",
            ", ".join(sorted(user2_shares[week] - user1_shares[week])),
        ]
        for week in sorted(set.intersection(set(user1_shares.keys()), set(user2_shares.keys())))
    ]

    return dict(user1=user1, user2=user2, data=json.dumps(data))


@app.route("/analytics/startlisten")
@cached_analytics_view
def analytics_startlisten():
    user = db.session.query(User).get(request.args.get("user", type=int))
    period_size = int(request.args.get("days")) * 86400

    first_scrobble_uts = db.session.query(func.min(Scrobble.uts)).filter_by(user=user).scalar()
    period_end = time.time() - period_size
    periods = []
    while period_end - period_size * 2 >= first_scrobble_uts:
        periods.append((period_end - period_size, period_end))
        period_end -= period_size
    periods.append((first_scrobble_uts, period_end))
    periods.reverse()

    artists = {}
    for (period_start, period_end) in periods:
        for (artist,) in db.session.query(Scrobble.artist).filter_by(user=user).filter((period_start <= Scrobble.uts), (Scrobble.uts < period_end)).group_by(Scrobble.artist).order_by(-func.count(Scrobble.id))[:int(request.args.get("n"))]:
            if artist in artists:
                continue

            day2scrobbles = dict([
                (day, 0)
                for day in range(
                    int(db.session.query(func.min(Scrobble.uts)).filter_by(user=user, artist=artist).scalar() / 86400),
                    int(db.session.query(func.max(Scrobble.uts)).filter_by(user=user, artist=artist).scalar() / 86400) + 1
                )
            ])
            for (uts, ) in db.session.query(Scrobble.uts).filter_by(user=user, artist=artist):
                day2scrobbles[int(uts / 86400)] += 1

            for day in day2scrobbles:
                if day2scrobbles[day] < 4:
                    day2scrobbles[day] = 0

            for day in sorted(day2scrobbles.keys()):
                if day2scrobbles[day] != 0:
                    break
                del day2scrobbles[day]
            for day in sorted(day2scrobbles.keys(), key=lambda day: -day):
                if day2scrobbles[day] != 0:
                    break
                del day2scrobbles[day]

            gaps = {}
            for day, scrobbles in day2scrobbles.items():
                gaps[day + 1] = 0
                gap_day = day + 1
                while gap_day in day2scrobbles and day2scrobbles[gap_day] == 0:
                    gaps[day + 1] += 1
                    gap_day += 1

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

            first_scrobble = db.session.query(Scrobble).filter_by(user=user, artist=artist).filter(Scrobble.uts >= first_scrobble_appx).order_by(Scrobble.uts)[0]
            totally_first_scrobble = db.session.query(Scrobble).filter_by(user=user, artist=artist).order_by(Scrobble.uts)[0]

            artists[first_scrobble.artist] = {
                "track"     :   first_scrobble.track,
                "datetime"  :   datetime.fromtimestamp(first_scrobble.uts),
            }
            if first_scrobble.uts != totally_first_scrobble.uts:
                artists[first_scrobble.artist]["totally_first_scrobble"] = {
                    "track"     :   totally_first_scrobble.track,
                    "datetime"  :   datetime.fromtimestamp(totally_first_scrobble.uts),
                }

    return {
        "navbar_active" :   "analytics",
        "title"         :   "Когда %(user)s начал слушать музыку?" % { "user" : user.username },
        "rows"          :   sorted(artists.items(), key=lambda t: t[1]["datetime"]),
    }


@app.route("/analytics/hitparade", methods=["GET", "POST"])
def analytics_hitparade():
    user = db.session.query(User).get(request.args.get("user"))
    year = int(request.args.get("year"))

    title = "Хит-парад %(user)s за %(year)s год" % {
        "user"  : user.username,
        "year"  : year,
    }
    year_start_uts = time.mktime(datetime(year=year, month=1, day=1).timetuple())
    year_end_uts = time.mktime(datetime(year=year, month=12, day=31, hour=23, minute=59, second=59).timetuple())

    track_albums_raw = func.group_concat(distinct(Scrobble.album).op("SEPARATOR")(literal_column('"@@@@@@"')))
    track_albums = lambda track_albums_raw: sorted(filter(None, track_albums_raw.split("@@@@@@")))

    if request.method != "POST":
        return render_template("analytics/hitparade.html", **{
            "title"         : title + ": шаг 1",

            "step"          : 1,
            "year"          : year,
            "artists"       : [
                                  (artist, scrobble_count, [(track, track_albums(albums_raw))
                                                            for track, albums_raw in db.session.query(
                                                                                                    Scrobble.track,
                                                                                                    track_albums_raw
                                                                                                ).\
                                                                                                filter(
                                                                                                    Scrobble.user_id == user.id,
                                                                                                    Scrobble.artist == artist,
                                                                                                    Scrobble.track.in_(map(operator.itemgetter(0), db.session.query(Scrobble.track).\
                                                                                                                                                              filter(
                                                                                                                                                                  Scrobble.artist == artist
                                                                                                                                                              ).\
                                                                                                                                                              group_by(Scrobble.track).\
                                                                                                                                                              having(
                                                                                                                                                                  func.min(Scrobble.uts) >= year_start_uts
                                                                                                                                                              ).\
                                                                                                                                                              all()))
                                                                                                ).\
                                                                                                group_by(Scrobble.track).\
                                                                                                order_by(func.min(Scrobble.uts)).\
                                                                                                all()])
                                  for artist, scrobble_count in db.session.query(Scrobble.artist, func.count(Scrobble.id)).\
                                                                           filter(
                                                                               Scrobble.user_id == user.id,
                                                                               Scrobble.uts >= year_start_uts,
                                                                               Scrobble.uts <= year_end_uts,
                                                                           ).\
                                                                           group_by(Scrobble.artist).\
                                                                           order_by(-func.count(Scrobble.id))\
                                                                           [:request.args.get("n")]
                              ]
        })
    else:
        if request.form.get("step") == "2":
            return render_template("analytics/hitparade.html", **{
                "title"             : title + ": шаг 2",

                "step"              : 2,
                "year"              : year,
                "artist_tracks"     : [
                    (artist, [
                        (track, track_albums(albums_raw), this_year_first_scrobble == db.session.query(func.min(Scrobble.uts)).\
                                                                                                 filter(
                                                                                                     Scrobble.user_id == user.id,
                                                                                                     Scrobble.artist == artist,
                                                                                                     Scrobble.track == track
                                                                                                 ).\
                                                                                                 scalar())
                        for track, albums_raw, this_year_first_scrobble in db.session.query(
                                                                                          Scrobble.track,
                                                                                          track_albums_raw,
                                                                                          func.min(Scrobble.uts)
                                                                                      ).\
                                                                                      filter(
                                                                                          Scrobble.user_id == user.id,
                                                                                          Scrobble.artist == artist,
                                                                                          Scrobble.uts >= year_start_uts,
                                                                                          Scrobble.uts <= year_end_uts
                                                                                      ).\
                                                                                      group_by(Scrobble.track).\
                                                                                      order_by(func.min(Scrobble.uts))
                    ])
                    for artist in request.form.getlist("artist")
                ]
            })

        if request.form.get("step") == "3":
            return render_template("analytics/hitparade.html", **{
                "title"             : title + ": шаг 3",

                "step"              : 3,
                "year"              : year,
                "artist_tracks"     : [
                    (artist, [
                        (track[len(artist) + 3:], request.form[track], db.session.query(ApproximateTrackLength).\
                                                                                  filter(
                                                                                      ApproximateTrackLength.artist == artist,
                                                                                      ApproximateTrackLength.track == track.replace(artist + " - ", "")
                                                                                  ).\
                                                                                  first())
                        for track in request.form.getlist("track")
                        if track.startswith(artist + " - ")
                    ])
                    for artist in request.form.getlist("artist")
                ]
            })

        if request.form.get("step") == "4":
            return render_template("analytics/hitparade.html", **{
                "title"             : title,

                "step"              : 4,
                "sort"              : request.args.get("sort"),
                # lol "let" analogue for python
                "parade"            : sorted([
                    [
                        (artist, album, tracks, sum([track[1] for track in tracks]),
                                                sum([track[3] for track in tracks]),
                                                sum([track[1] for track in tracks]) / float(year_end_uts - min([track[4] for track in tracks])) * 86400,
                                                sum([track[3] for track in tracks]) / float(year_end_uts - min([track[4] for track in tracks])) * 86400,
                                                numpy.mean(map(operator.itemgetter(1), tracks)),
                                                numpy.mean(map(operator.itemgetter(1), tracks)) * sum(map(operator.itemgetter(2), tracks)),
                                                (numpy.median(map(operator.itemgetter(1), tracks)) + numpy.mean(map(operator.itemgetter(1), tracks)) / 1000.0),
                                                (numpy.median(map(operator.itemgetter(1), tracks)) + numpy.mean(map(operator.itemgetter(1), tracks)) / 1000.0) * sum(map(operator.itemgetter(2), tracks)))
                        for artist, album, tracks in
                        [(artist, album, sorted([
                            [
                                (track, scrobbles, length, scrobbles * length, first_scrobble, last_scrobble)
                                for track, scrobbles, first_scrobble, last_scrobble, length in
                                [(request.form.getlist("track")[i].replace(artist + " - ", ""),) + db.session.query(func.count(Scrobble), func.min(Scrobble.uts), func.max(Scrobble.uts)).filter(
                                    Scrobble.user_id == user.id,
                                    Scrobble.artist == artist,
                                    Scrobble.track == request.form.getlist("track")[i].replace(artist + " - ", ""),
                                    Scrobble.uts >= year_start_uts,
                                    Scrobble.uts <= year_end_uts
                                )[0] + (int(request.form.getlist("length_m")[i]) * 60 + int(request.form.getlist("length_s")[i]),)]
                            ][0]
                            for i in range(0, len(request.form.getlist("track")))
                            if request.form.getlist("track")[i].startswith(artist + " - ") and\
                               request.form.getlist("album")[i] == album
                        ], key=lambda track_scrobbles_length_total: -track_scrobbles_length_total[3]))]
                    ][0]
                    for artist, album in itertools.chain(*[
                        [
                            (artist, album)
                            for album in set([v for i, v in enumerate(request.form.getlist("album"))
                                                if request.form.getlist("track")[i].startswith(artist + " - ")])
                        ]
                        for artist in request.form.getlist("artist")
                    ])
                ], key={
                    "scrobbles"         : lambda artist_album_tracks_scrobbles_length_scrobblesADay_lengthADay_mean_meanWithTime_median_medianWithTime: -artist_album_tracks_scrobbles_length_scrobblesADay_lengthADay_mean_meanWithTime_median_medianWithTime[3],
                    "scrobbles_a_day"   : lambda artist_album_tracks_scrobbles_length_scrobblesADay_lengthADay_mean_meanWithTime_median_medianWithTime: -artist_album_tracks_scrobbles_length_scrobblesADay_lengthADay_mean_meanWithTime_median_medianWithTime[5],
                    "length"            : lambda artist_album_tracks_scrobbles_length_scrobblesADay_lengthADay_mean_meanWithTime_median_medianWithTime: -artist_album_tracks_scrobbles_length_scrobblesADay_lengthADay_mean_meanWithTime_median_medianWithTime[4],
                    "length_a_day"      : lambda artist_album_tracks_scrobbles_length_scrobblesADay_lengthADay_mean_meanWithTime_median_medianWithTime: -artist_album_tracks_scrobbles_length_scrobblesADay_lengthADay_mean_meanWithTime_median_medianWithTime[6],
                    "mean"              : lambda artist_album_tracks_scrobbles_length_scrobblesADay_lengthADay_mean_meanWithTime_median_medianWithTime: -artist_album_tracks_scrobbles_length_scrobblesADay_lengthADay_mean_meanWithTime_median_medianWithTime[7],
                    "mean_with_time"    : lambda artist_album_tracks_scrobbles_length_scrobblesADay_lengthADay_mean_meanWithTime_median_medianWithTime: -artist_album_tracks_scrobbles_length_scrobblesADay_lengthADay_mean_meanWithTime_median_medianWithTime[8],
                    "median"            : lambda artist_album_tracks_scrobbles_length_scrobblesADay_lengthADay_mean_meanWithTime_median_medianWithTime: -artist_album_tracks_scrobbles_length_scrobblesADay_lengthADay_mean_meanWithTime_median_medianWithTime[9],
                    "median_with_time"  : lambda artist_album_tracks_scrobbles_length_scrobblesADay_lengthADay_mean_meanWithTime_median_medianWithTime: -artist_album_tracks_scrobbles_length_scrobblesADay_lengthADay_mean_meanWithTime_median_medianWithTime[10],
                }[request.args.get("sort")])
            })


@app.route("/analytics/track_length_artist_top")
@cached_analytics_view
def analytics_track_length_artist_top():
    user = db.session.query(User).get(int(request.args.get("user")))

    return dict(user=user, top=[
        (artist, timedelta_in_words(int(length), 2))
        for artist, length in db.session.query(Scrobble.artist, func.sum(ApproximateTrackLength.length)).\
                                         outerjoin((ApproximateTrackLength, Scrobble.approximate_track_length)).\
                                         filter(Scrobble.user == user, ApproximateTrackLength.track != None).\
                                         group_by(Scrobble.artist).\
                                         order_by(-func.sum(ApproximateTrackLength.length))
                                         [:1000]
    ])


@app.route("/analytics/time_spent_to_music")
@cached_analytics_view
def analytics_time_spent_to_music():
    return dict(users=[
        (db.session.query(User).get(user_id), timedelta_in_words(int(time_spent), 2))
        for user_id, time_spent in db.session.query(Scrobble.user_id, func.sum(ApproximateTrackLength.length)).\
                                              outerjoin((ApproximateTrackLength, Scrobble.approximate_track_length)).\
                                              group_by(Scrobble.user_id).\
                                              order_by(-func.sum(ApproximateTrackLength.length))
    ])


@app.route("/analytics/coincidences")
@cached_analytics_view
def analytics_coincidences():
    coincidences = []
    doves = defaultdict(lambda: 0)
    for coincidence in db.session.query(Coincidence).all():
        users_uts = map(lambda s: map(int, s.split(":")), coincidence.users_uts.split(";"))

        users = map(db.session.query(User).get, map(operator.itemgetter(0), users_uts))

        coincidences.append((
            coincidence,
            datetime.fromtimestamp(users_uts[0][1]),
            ", ".join([user.username for user in users]),
            "#%02x0000" % int((300 - float(sum([user_uts[1] - users_uts[0][1] for user_uts in users_uts[1:]])) / (len(users_uts) - 1)) / 300 * 255),
        ))

        doves[", ".join(sorted([user.username for user in users]))] += 1

    return dict(coincidences=coincidences, doves=sorted(filter(lambda (k, v): v >= 10, doves.items()), key=lambda (k, v): -v))


@app.route("/analytics/first_users_by_artist")
@cached_analytics_view
def analytics_first_users_by_artist():
    us = request.args.getlist("us", type=int)
    them = request.args.getlist("them", type=int)
    min_scrobbles = request.args.get("min_scrobbles", type=int)
    user2artist2scrobbles = get_user2artist2scrobbles(us + them, min_scrobbles)
    user2artistlower2scrobbles = get_user2artistlower2scrobbles(user2artist2scrobbles)

    user2username = get_user2username()

    artist2first_users = {artist: map(operator.itemgetter(1),
                                      filter(lambda (i, user_id): i == 0 or user_id in us,
                                             enumerate(sorted(filter(lambda user_id: artist.lower() in user2artistlower2scrobbles[user_id],
                                                                     unique_items(us + them)),
                                                              key=lambda user: -user2artistlower2scrobbles[user][artist.lower()]))))
                          for artist in unique_items(sum((v.keys() for v in user2artist2scrobbles.values()), []),
                                                     key=lambda artist: artist.lower())}
    user2artists = [(user2username[user_id],
                     sorted([(artist,
                              user2artistlower2scrobbles[user_id][artist.lower()],
                              ((user2username[first_users[1]],
                                user2artistlower2scrobbles[first_users[1]][artist.lower()])
                               if len(first_users) > 1
                               else None))
                             for artist, first_users in artist2first_users.iteritems()
                             if first_users[0] == user_id],
                            key=lambda (a, b, c): -b))
                    for user_id in sorted(us, key=lambda id: user2username[id])]

    return dict(title="Пользователи, первые по количеству прослушиваний исполнителей",
                user2artists=user2artists)
