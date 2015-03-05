# -*- coding=utf-8 -*-
from __future__ import absolute_import, division, unicode_literals

from bs4 import BeautifulSoup
from datetime import date
from flask import *
import logging
import pylast
import requests

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
def dashboard():
    return render_template("dashboard.html")


@app.route("/dashboard/artist")
@dashboard_cache("artist")
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
