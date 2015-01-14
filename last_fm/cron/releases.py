# -*- coding=utf-8 -*-
from __future__ import absolute_import, division, unicode_literals

from datetime import datetime, timedelta
import dateutil.parser
import feedparser
import logging
from lxml import objectify
import re
import socket
from sqlalchemy.sql import func
import urllib
import urllib2
import whatapi

from themyutils.misc import retry

from last_fm.app import app
from last_fm.celery import cron
from last_fm.db import db
from last_fm.models import *
from last_fm.utils.model import get_artist_id, get_user_artists

logger = logging.getLogger(__name__)


@cron.job(minute="*/15")
def update_releases():
    socket.setdefaulttimeout(10)
    for feed in db.session.query(ReleaseFeed):
        try:
            for release in find_releases(feed):
                if db.session.query(func.count(Release.id)).filter_by(title=release.title).scalar() == 0:
                    release.feed = feed
                    release.date = datetime.now()
                    db.session.add(release)
        except:
            logging.exception("Error downloading feed %s", feed.url)

    db.session.commit()


def find_releases(feed):
    if feed.url == "what.cd":
        api = whatapi.WhatAPI(username=app.config["WHAT_CD_USERNAME"], password=app.config["WHAT_CD_PASSWORD"])
        for group in api.request("browse", searchstr="")["response"]["results"]:
            if "torrents" not in group:
                continue

            if min(dateutil.parser.parse(torrent["time"]).year
                   for torrent in group["torrents"]) < datetime.now().year:
                continue

            release = Release()
            release.url = "https://what.cd/torrents.php?id=%d" % group["groupId"]
            release.title = " - ".join(filter(None, [group.get(k) for k in ("artist", "groupName")]))
            if group.get("groupYear"):
                release.title += " (%d)" % group.get("groupYear")
            release.content = ""
            yield release
        return

    for post in feedparser.parse(feed.url)["items"]:
        release = Release()
        release.url = post["link"]
        release.title = post["title"]
        try:
            release.content = u"".join([c["value"] for c in post["content"]])
        except:
            release.content = post["summary"]
        yield release


@cron.job(hour=5, minute=0)
def update_user_artists():
    session = db.create_scoped_session()
    users = list(session.query(User).\
                         filter(User.download_scrobbles == False,
                                (User.last_library_update == None) |\
                                    (User.last_library_update <= datetime.now() - timedelta(days=7))))
    session.remove()

    for u in users:
        session = db.create_scoped_session()
        artist_session = db.create_scoped_session()

        user = session.query(User).get(u.id)

        session.query(UserArtist).\
                filter(UserArtist.user == user).\
                delete()

        page = 1
        pages = -1
        while pages == -1 or page <= pages:
            logger.debug("Opening %s's page %d of %d", user.username, page, pages)
            xml = retry(lambda: objectify.fromstring(
                urllib2.urlopen("http://ws.audioscrobbler.com/2.0/?" + urllib.urlencode(dict(method="library.getArtists",
                                                                                             api_key=app.config["LAST_FM_API_KEY"],
                                                                                             user=user.username,
                                                                                             limit=200,
                                                                                             page=page))).read(),
                objectify.makeparser(encoding="utf-8", recover=True)
            ), max_tries=5, exceptions=((urllib2.HTTPError, lambda e: e.code not in [400]),), logger=logger)

            if pages == -1:
                pages = int(xml.artists.get("totalPages"))

            for artist in xml.artists.iter("artist"):
                user_artist = UserArtist()
                user_artist.user = user
                user_artist.artist_id = get_artist_id(artist_session, unicode(artist.name))
                user_artist.scrobbles = int(artist.playcount)
                session.add(user_artist)

                user.last_library_update = datetime.now()

            page = page + 1

        artist_session.commit()
        session.commit()


@cron.job(hour="*/2", minute=0)
def update_user_releases():
    not_w = re.compile("\W", flags=re.UNICODE)
    comparable_str = lambda s: re.sub(not_w, "", s.lower())

    for u in db.session.query(User).\
                        filter(User.build_releases == True):
        session = db.create_scoped_session()

        user = session.query(User).get(u.id)

        session.query(UserRelease).\
                filter(UserRelease.user == user).\
                delete()

        artists = filter(lambda t: len(t[0]) > 3, [(comparable_str(artist), artist, scrobbles)
                                                   for artist, scrobbles in get_user_artists(user, min_scrobbles=10)])
        for release in session.query(Release).\
                               join(ReleaseFeed).\
                               filter(Release.date > datetime.now() - timedelta(days=30),
                                      ((ReleaseFeed.private == False) |
                                       (ReleaseFeed.id.in_([f.id for f in u.private_release_feeds])))).\
                               order_by(Release.id.desc()):
            release_title = comparable_str(release.title)

            for prefix, artist, scrobbles in artists:
                if release_title.startswith(prefix):
                    user_release = UserRelease()
                    user_release.user = user
                    user_release.release = release
                    user_release.artist = artist
                    user_release.artist_scrobbles = scrobbles
                    session.add(user_release)
                    break

        session.commit()

