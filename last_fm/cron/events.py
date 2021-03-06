# -*- coding=utf-8 -*-
from __future__ import absolute_import, division, unicode_literals

import dateutil.parser
import logging
from lxml import objectify
import urllib
import urllib2

from themyutils.misc import retry

from last_fm.app import app
from last_fm.celery import cron
from last_fm.db import db
from last_fm.models import *

logger = logging.getLogger(__name__)


@cron.job(hour=5, minute=0)
def update_events():
    artists = set([user_artist.artist.name
                   for user_artist in db.session.query(UserArtist).\
                                                 filter(UserArtist.scrobbles >= 100,
                                                        UserArtist.user_id.in_([6, 11]))])
    try:
        for artist in artists:
            db_artist = db.session.query(Artist).filter(Artist.name == artist).one()

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

                    db_event = db.session.query(Event).get(int(event.id))
                    if db_event:
                        if db_artist in db_event.artists:
                            found = True
                            break
                        else:
                            db_event.artists.append(db_artist)
                    else:
                        db_event = Event()
                        db_event.id = int(event.id)
                        db_event.title = unicode(event.title)
                        db_event.datetime = dateutil.parser.parse(unicode(event.startDate))
                        db_event.url = unicode(event.url)
                        db_event.city = unicode(event.venue.location.city)
                        db_event.country = unicode(event.venue.location.country)
                        db_event.artists.append(db_artist)
                        db.session.add(db_event)

                if found:
                    break

                page = page + 1

            db.session.commit()
    except urllib2.HTTPError:
        pass
