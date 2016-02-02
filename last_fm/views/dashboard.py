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
import sys
import time
import urllib

from themyutils.datetime import russian_strftime
from themyutils.itertools import with_prev
from themyutils.sqlalchemy import entity_to_dict
from twitter_overkill.utils import join_list

from last_fm.app import app
from last_fm.db import db
from last_fm.models import *
from last_fm.utils.model import get_artist

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
    db_artist = get_artist(artist)

    url = "http://www.last.fm/ru/music/%s" % urllib.quote(artist.encode("utf-8")).replace("%2B", "%252B")
    artist_wiki = BeautifulSoup(requests.get(url + "/+wiki").text)
    artist_comments = BeautifulSoup(requests.get(url + "/comments").text)

    hash = None
    images = []
    for i in xrange(sys.maxint):
        artist_images = BeautifulSoup(requests.get(url + "/+images" + (("/" + hash) if hash is not None else "")).text)

        new_images = [src
                      for src in [img["src"].replace("60x60", "ar0")
                                  for img in artist_images.select("ul.gallery-thumbnails img")]
                      if src not in images]
        if new_images:
            db_new_images = [url
                             for (url,) in db.session.query(ArtistImage.url).\
                                                      filter(ArtistImage.artist == db_artist,
                                                             ArtistImage.url.in_(new_images))]
            really_new_images = set(new_images) - set(db_new_images)
            if really_new_images:
                for image in really_new_images:
                    db_image = ArtistImage()
                    db_image.artist = db_artist
                    db_image.url = image
                    db.session.add(db_image)
            else:
                break
            images += new_images
            hash = new_images[-1].split("/")[-1]
            logger.debug("Downloaded %d images for %s, going for %s", len(images), artist, hash)
        else:
            break
    db.session.commit()

    return {"wiki": "".join(map(unicode, artist_wiki.select(".wiki-content")[0].contents))
                    if artist_wiki.select(".wiki-content") else "",
            "images": [url for (url,) in db.session.query(ArtistImage.url).\
                                                    filter(ArtistImage.artist == db_artist)],
            "shouts": [{"username": shout.select(".text-container .username")[0].text.strip(),
                        "avatar": shout.select("img.avatar")[0]["src"],
                        "contents": unicode(shout.select(".comment-text")[0].text.strip()),
                        "date": shout.select(".timestamp")[0].text.strip()}
                       for shout in artist_comments.select("li.comment-container")]}


@app.route("/dashboard/stats")
@login_required
def dashboard_stats():
    artist = request.args["artist"]
    track = request.args["track"]
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
    next_get_info = "Темпами этой недели, <b>%s</b> GET будет <b>%s</b>, этого месяца — <b>%s</b>" % (
        "{0:,}".format(next_get).replace(",", " "),
        russian_strftime(datetime.now() + timedelta(days=scrobbles_till_next_get / scrobbles_per_day_last_week),
                         "%d %B %Y").replace(datetime.now().strftime(" %Y"), ""),
        russian_strftime(datetime.now() + timedelta(days=scrobbles_till_next_get / scrobbles_per_day_last_month),
                         "%d %B %Y").replace(datetime.now().strftime(" %Y"), ""),
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
    next_artist_get_info = "Темпами этой недели, <b>%s</b> GET будет <b>%s</b>, этого месяца — <b>%s</b>, полугодия — <b>%s</b>" % (
        "{0:,}".format(next_get).replace(",", " "),
        russian_strftime(datetime.now() + timedelta(days=scrobbles_till_next_get / scrobbles_per_day_last_week),
                         "%d %B %Y").replace(datetime.now().strftime(" %Y"), ""),
        russian_strftime(datetime.now() + timedelta(days=scrobbles_till_next_get / scrobbles_per_day_last_month),
                         "%d %B %Y").replace(datetime.now().strftime(" %Y"), ""),
        russian_strftime(datetime.now() + timedelta(days=scrobbles_till_next_get / scrobbles_per_day_last_half_year),
                         "%d %B %Y").replace(datetime.now().strftime(" %Y"), ""),
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
                    winning_line += "не догоните <b>%s</b> <b>никогда</b>" % _closest_winning_enemy.username
                else:
                    winning_line += "не догоните <b>никогда</b>"
                prev_winning_was_never = True
            else:
                if i == 0:
                    winning_line += "догоните <b>%s</b> " % (_closest_winning_enemy.username)
                else:
                    if prev_winning_was_never:
                        winning_line += "догоните "

                winning_line += russian_strftime(datetime.now() + timedelta(
                    days=(closest_winning_enemy_scrobbles - my_scrobbles) / (my_tempo - winning_tempo)),
                                                 "<b>%d %B %Y</b>").replace(datetime.now().strftime(" %Y"), "")

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
                    losing_line += "<b>%s</b> не догонит вас <b>никогда</b>" % _closest_losing_enemy.username
                else:
                    losing_line += "не догонит <b>никогда</b>"
                prev_winning_was_never = True
            else:
                if i == 0:
                    losing_line += "<b>%s</b> догонит вас " % _closest_losing_enemy.username
                else:
                    if prev_winning_was_never:
                        losing_line += "догонит "
                losing_line_interesting = True

                losing_line += russian_strftime(datetime.now() + timedelta(
                    days=(my_scrobbles - closest_losing_enemy_scrobbles) / (losing_tempo - my_tempo)),
                                                 "<b>%d %B %Y</b>").replace(datetime.now().strftime(" %Y"), "")

    users_who_know_this_track = []
    users_who_dont_know_this_track = []
    for (u,) in db.session.query(Scrobble.user_id).\
                           group_by(Scrobble.user_id).\
                           filter(Scrobble.artist == artist,
                                  ~Scrobble.user_id.in_([11])).\
                           having(func.count(Scrobble.id) > 100):
        _u = db.session.query(User).get(u)
        if db.session.query(func.count(Scrobble.id)).filter(Scrobble.user == _u,
                                                            Scrobble.artist == artist,
                                                            Scrobble.track == track).scalar() > 0:
            users_who_know_this_track.append("<b>" + _u.username + "</b>")
        else:
            users_who_dont_know_this_track.append("<b>" + _u.username + "</b>")
    users_track = ""
    if len(users_who_know_this_track) > 0:
        users_track += "%s %s %s" % (join_list(users_who_know_this_track),
                                     "слышали" if len(users_who_know_this_track) > 1 else "слышал",
                                     track)
        if len(users_who_dont_know_this_track) > 0:
            users_track += ", а вот "
    if len(users_who_dont_know_this_track) > 0:
        if len(users_who_know_this_track) > 0:
            users_track += "%s — нет" % (join_list(users_who_dont_know_this_track))
        else:
            users_track += "%s %s %s" % (join_list(users_who_dont_know_this_track),
                                         "не слышали" if len(users_who_dont_know_this_track) > 1 else "не слышал",
                                         track)

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
