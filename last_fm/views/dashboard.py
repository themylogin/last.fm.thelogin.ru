# -*- coding=utf-8 -*-
from __future__ import absolute_import, division, unicode_literals

from bs4 import BeautifulSoup
from datetime import date, datetime, timedelta
from dateutil.relativedelta import relativedelta
from flask import *
from flask.ext.security import current_user, login_required
import itertools
import logging
import math
import pylast
import requests
from sqlalchemy.sql import func
import time

from themyutils.datetime import russian_strftime
from themyutils.itertools import with_prev
from themyutils.sqlalchemy import entity_to_dict

from last_fm.app import app
from last_fm.db import db
from last_fm.models import *
from last_fm.utils.network import get_network

logger = logging.getLogger(__name__)

__all__ = []


def dashboard_cache(key_name):
    def decorator(view):
        def decorated():
            key = request.args[key_name]
            today = date.today()
            o = db.session.query(DashboardData).filter(DashboardData.type == key_name,
                                                       DashboardData.key == key,
                                                       DashboardData.date == today).first()
            if o is None:
                o = DashboardData()
                o.type = key_name
                o.key = key
                o.value = view(key)
                o.date = today
                db.session.add(o)
                db.session.commit()

            return jsonify(o.value)

        decorated.__name__ = view.__name__
        return decorated

    return decorator


@app.route("/dashboard")
@login_required
def dashboard():
    return render_template("dashboard.html")


@app.route("/dashboard/artist")
@dashboard_cache("artist")
@login_required
def dashboard_artist(artist):
    network = get_network()
    artist = network.get_artist(artist)
    url = artist.get_url(pylast.DOMAIN_RUSSIAN)
    artist_page = BeautifulSoup(requests.get(url).text)
    artist_wiki = BeautifulSoup(requests.get(url + "/+wiki").text)

    page = 1
    pages = 1
    images = []
    while page <= pages:
        artist_images = BeautifulSoup(requests.get(url + "/+images?page=%d" % page).text)

        images += [img["src"].replace("126s", "_") for img in artist_images.select("#pictures img")]

        nav = filter(lambda a: "btn--icon-only" not in a["class"], artist_images.select(".whittle-pagination a"))
        if nav:
            pages = int(nav[-1].text.strip())

        page += 1

    return {"wiki": "".join(map(unicode, artist_wiki.select("#wiki")[0].contents)),
            "images": images,
            "shouts": [{"username": shout.select(".author")[0].text.strip(),
                        "avatar": shout.select(".author img")[0]["src"],
                        "contents": "".join(sum([map(unicode, p.contents) for p in shout.select("p")], [])),
                        "date": shout.select(".date")[0].text.strip()}
                       for shout in artist_page.select(".artist-shoutbox li.message")]}


@app.route("/dashboard/artist/stats")
@login_required
def dashboard_artist_stats():
    artist = request.args["artist"]
    user = current_user

    try:
        first_real_scrobble_uts, first_scrobble_uts = db.session.query(UserArtist.first_real_scrobble,
                                                                       UserArtist.first_scrobble).\
                                                                 join(Artist).\
                                                                 filter(Artist.name == artist,
                                                                        UserArtist.user == user).\
                                                                 one()
    except Exception:
        first_scrobble_uts = db.session.query(func.min(Scrobble.uts)).\
                                        filter(Scrobble.user == user,
                                               Scrobble.artist == artist).\
                                        scalar()
        first_real_scrobble_uts = first_scrobble_uts

    """
    _period_size = int((time.time() - first_scrobble_uts) / 50)
    _chart_data = dict(db.session.query(Scrobble.uts.op("div")(_period_size),
                                        func.count(Scrobble.id)).\
                                  filter(Scrobble.user == user,
                                         Scrobble.artist == artist).\
                                  group_by(Scrobble.uts.op("div")(_period_size)))
    chart_labels = []
    chart_data = []
    for k, prev_k in with_prev(range(min(_chart_data.keys()), max(_chart_data.keys()) + 1)):
        k_d = datetime.fromtimestamp(k * _period_size)
        prev_k_d = datetime.fromtimestamp(prev_k * _period_size)if prev_k else None
        chart_labels.append(k_d.strftime("%Y.%m") if prev_k_d is None else\
                            k_d.strftime("%Y") if prev_k_d.year != k_d.year else\
                            k_d.strftime("%m") if prev_k_d.month != k_d.month else\
                            "")
        chart_data.append(_chart_data.get(k, 0))
    """

    scrobbles_per_day_last_week = db.session.query(func.count(Scrobble.id)).\
                                             filter(Scrobble.user == user,
                                                    Scrobble.uts > time.mktime(
                                                         (datetime.now() - timedelta(days=7)).timetuple())).\
                                             scalar() / 7 or 1
    scrobbles_per_day_last_month = db.session.query(func.count(Scrobble.id)).\
                                              filter(Scrobble.user == user,
                                                     Scrobble.uts > time.mktime(
                                                         (datetime.now() - timedelta(days=30)).timetuple())).\
                                              scalar() / 30 or 1
    total_scrobbles = db.session.query(func.count(Scrobble.id)).\
                                 filter(Scrobble.user == user).\
                                 scalar()
    next_get = int(math.ceil(total_scrobbles / 10000) * 10000)
    scrobbles_till_next_get = next_get - total_scrobbles
    next_get_info = "Темпами этой недели, %s GET будет %s, этого месяца — %s" % (
        "{0:,}".format(next_get).replace(",", " "),
        russian_strftime(datetime.now() + timedelta(days=scrobbles_till_next_get / scrobbles_per_day_last_week),
                         "%d %B %Y"),
        russian_strftime(datetime.now() + timedelta(days=scrobbles_till_next_get / scrobbles_per_day_last_month),
                         "%d %B %Y"),
    )

    scrobbles_per_day_last_week = _user_scrobbling_tempo(7, user, artist)
    scrobbles_per_day_last_month = _user_scrobbling_tempo(30, user, artist)
    scrobbles_per_day_last_half_year = _user_scrobbling_tempo(180, user, artist)
    total_scrobbles = db.session.query(func.count(Scrobble.id)).\
                                 filter(Scrobble.user == user,
                                        Scrobble.artist == artist).\
                                 scalar()
    next_get = next(itertools.dropwhile(lambda get: total_scrobbles > get,
                                              itertools.chain([666], itertools.count(1000, 1000))))
    scrobbles_till_next_get = next_get - total_scrobbles
    next_artist_get_info = "Темпами этой недели, %s GET будет %s, этого месяца — %s, полугодия — %s" % (
        "{0:,}".format(next_get).replace(",", " "),
        russian_strftime(datetime.now() + timedelta(days=scrobbles_till_next_get / scrobbles_per_day_last_week),
                         "%d %B %Y"),
        russian_strftime(datetime.now() + timedelta(days=scrobbles_till_next_get / scrobbles_per_day_last_month),
                         "%d %B %Y"),
        russian_strftime(datetime.now() + timedelta(days=scrobbles_till_next_get / scrobbles_per_day_last_half_year),
                         "%d %B %Y"),
    )
    next_artist_get_info_interesting = any(d < timedelta(days=365)
                                           for d in [timedelta(days=scrobbles_till_next_get / scrobbles_per_day_last_week),
                                                     timedelta(days=scrobbles_till_next_get / scrobbles_per_day_last_month),
                                                     timedelta(days=scrobbles_till_next_get / scrobbles_per_day_last_half_year)])

    my_scrobbles = _user_scrobbles(user, artist)
    closest_winning_enemy = db.session.query(Scrobble.user_id).\
                                       join(User).\
                                       filter(Scrobble.artist == artist).\
                                       having(func.count(Scrobble.id) > my_scrobbles).\
                                       group_by(Scrobble.user_id).\
                                       order_by(func.count(Scrobble.id).asc()).\
                                       first()
    if closest_winning_enemy:
        _closest_winning_enemy = db.session.query(User).get(closest_winning_enemy)
        closest_winning_enemy_scrobbles = _user_scrobbles(_closest_winning_enemy, artist)
    closest_losing_enemy = db.session.query(Scrobble.user_id).\
                                      join(User).\
                                      filter(Scrobble.artist == artist).\
                                      having(func.count(Scrobble.id) < my_scrobbles).\
                                      group_by(Scrobble.user_id).\
                                      order_by(func.count(Scrobble.id).desc()).\
                                      first()
    if closest_losing_enemy:
        _closest_losing_enemy = db.session.query(User).get(closest_losing_enemy)
        closest_losing_enemy_scrobbles = _user_scrobbles(_closest_losing_enemy, artist)
    winning_line = ""
    losing_line = ""
    losing_line_interesting = False
    prev_winning_was_never = None
    prev_losing_was_never = None
    for i, (days, desc) in enumerate([(7, ("этой", "недели")),
                                      (30, ("этого", "месяца")),
                                      (180, ("этого", "полугодия"))]):
        my_tempo = _user_scrobbling_tempo(days, user, artist)

        if closest_winning_enemy:
            winning_tempo = _user_scrobbling_tempo(days, _closest_winning_enemy, artist)

            if i == 0:
                winning_line += "Темпами %s %s вы " % desc
            elif i == 1:
                winning_line += ", %s %s — " % desc
            else:
                winning_line += ", %s — " % desc[1]

            if winning_tempo >= my_tempo:
                if i == 0:
                    winning_line += "не догоните %s никогда" % _closest_winning_enemy.username
                else:
                    winning_line += "не догоните никогда"
                prev_winning_was_never = True
            else:
                if i == 0:
                    winning_line += "догоните %s " % (_closest_winning_enemy.username)
                else:
                    if prev_winning_was_never:
                        winning_line += "догоните "

                winning_line += russian_strftime(datetime.now() + timedelta(
                    days=(closest_winning_enemy_scrobbles - my_scrobbles) / (my_tempo - winning_tempo)),
                                                 "%d %B %Y")

        if closest_losing_enemy:
            losing_tempo = _user_scrobbling_tempo(days, _closest_losing_enemy, artist)

            if i == 0:
                losing_line += "Темпами %s %s " % desc
            elif i == 1:
                losing_line += ", %s %s — " % desc
            else:
                losing_line += ", %s — " % desc[1]

            if my_tempo >= losing_tempo:
                if i == 0:
                    losing_line += "%s не догонит вас никогда" % _closest_losing_enemy.username
                else:
                    losing_line += "не догонит никогда"
                prev_winning_was_never = True
            else:
                if i == 0:
                    losing_line += "%s догонит вас " % _closest_losing_enemy.username
                else:
                    if prev_winning_was_never:
                        losing_line += "догонит "
                losing_line_interesting = True

                losing_line += russian_strftime(datetime.now() + timedelta(
                    days=(my_scrobbles - closest_losing_enemy_scrobbles) / (losing_tempo - my_tempo)),
                                                 "%d %B %Y")


    return jsonify({k: v
                    for k, v in locals().iteritems()
                    if not (k.startswith("_") or k in {"user"})})


def _user_scrobbles(user, artist):
    return db.session.query(func.count(Scrobble.id)).\
                      filter(Scrobble.user == user,
                             Scrobble.artist == artist).\
                      scalar()


def _user_scrobbling_tempo(days, user, artist=None):
    filter_args = [Scrobble.uts > time.mktime((datetime.now() - timedelta(days=days)).timetuple()),
                   Scrobble.user == user]
    if artist:
        filter_args.append(Scrobble.artist == artist)

    return (db.session.query(func.count(Scrobble.id)).\
                       filter(*filter_args).\
                       scalar() or 1) / days


@app.route("/dashboard/no_music")
@login_required
def dashboard_no_music():
    scrobbles_for_years = []
    for years in itertools.count(1):
        start = date.today() - relativedelta(years=years)
        end = start + timedelta(days=1)
        scrobbles = map(lambda scrobble: dict(time=scrobble.datetime.strftime("%H:%M"),
                                              **entity_to_dict(scrobble)),
                        db.session.query(Scrobble).\
                                   filter(Scrobble.uts >= time.mktime(start.timetuple()),
                                          Scrobble.uts < time.mktime(end.timetuple()),
                                          Scrobble.user == current_user).\
                                   order_by(Scrobble.uts))
        if scrobbles:
            scrobbles_grouped = []
            for album, group in itertools.groupby(scrobbles, lambda scrobble: scrobble["album"]):
                group = list(group)
                if album and len(group) > 1:
                    scrobbles_grouped.append({"class": "album",
                                              "title": "%s – %s" % (group[0]["artist"], album),
                                              "time": group[0]["time"]})
                else:
                    scrobbles_grouped.append({"class": "track",
                                              "title": "%s – %s" % (group[0]["artist"], group[0]["track"]),
                                              "time": group[0]["time"]})

            scrobbles_for_years.append({"year": start.year,
                                        "scrobbles": scrobbles,
                                        "scrobbles_grouped": scrobbles_grouped})
        else:
            if db.session.query(func.count(Scrobble)).\
                          filter(Scrobble.uts < time.mktime(start.timetuple()),
                                 Scrobble.user == current_user).\
                          scalar() == 0:
                break

    return jsonify(scrobbles_for_years=scrobbles_for_years)
