# -*- coding=utf-8 -*-
from __future__ import absolute_import, division, unicode_literals

from datetime import datetime, timedelta
import dateutil.parser
import feedparser
import HTMLParser
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


@cron.job(hour=5, minute=0)
def update_events():
    artists = set([user_artist.artist.name
                   for user_artist in db.session.query(UserArtist).\
                                                 filter(UserArtist.scrobbles >= 250,
                                                        UserArtist.user_id.in_([6, 11]))])
    for artist in artists:
        page = 1
        pages = -1
        while pages == -1 or page <= pages:
            logger.debug("Opening %s's page %d of %d", artist, page, pages)
            xml = retry(lambda: objectify.fromstring(
                urllib2.urlopen("http://ws.audioscrobbler.com/2.0/?" + urllib.urlencode(dict(method="artist.getPastEvents",
                                                                                             api_key=app.config["LAST_FM_API_KEY"],
                                                                                             artist=artist.encode("utf-8"),
                                                                                             page=page))).read(),
                objectify.makeparser(encoding="utf-8", recover=True)
            ), max_tries=5, exceptions=((urllib2.HTTPError, lambda e: e.code not in [400]),), logger=logger)

            if pages == -1:
                pages = int(xml.events.get("totalPages"))

            found = False
            for event in xml.events.iter("event"):
                if not hasattr(event, "venue"):
                    continue

                if db.session.query(Event).get(int(event.id)) is not None:
                    found = True
                    break

                db_event = Event()
                db_event.id = int(event.id)
                db_event.title = unicode(event.title)
                db_event.datetime = dateutil.parser.parse(unicode(event.startDate))
                db_event.url = unicode(event.url)
                db_event.city  = unicode(event.venue.location.city)
                db_event.country =  unicode(event.venue.location.country)
                for xml_artist in event.artists.iter("artist"):
                    db_artist = db.session.query(Artist).filter(Artist.name == unicode(xml_artist)).first()
                    if db_artist is None:
                        db_artist = Artist()
                        db_artist.name = unicode(xml_artist)
                    db_event.artists.append(db_artist)
                db.session.add(db_event)
                db.session.commit()

            if found:
                break

            page = page + 1
