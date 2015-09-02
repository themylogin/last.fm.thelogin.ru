# -*- coding=utf-8 -*-
from __future__ import absolute_import, division, unicode_literals

from bs4 import BeautifulSoup
import logging
import re
import requests
from sqlalchemy.sql import func

from last_fm.celery import cron
from last_fm.db import db
from last_fm.models import *
from last_fm.utils.model import update_scrobbles_for_user
from last_fm.utils.network import get_network
from last_fm.utils.twitter import post_tweet

logger = logging.getLogger(__name__)


@cron.job(minute="*/5")
def tweet_gets():
    session = db.create_scoped_session()

    for user in session.query(User).\
                        filter(User.download_scrobbles == True,
                               User.twitter_username != None,
                               User.twitter_track_gets == True):
        for get in map(lambda x: x * 10000, range(1, int(session.query(func.count(Scrobble.id)).\
                                                                 filter(Scrobble.user == user).\
                                                                 scalar() / 10000) + 1)):
            if session.query(Get).\
                       filter(Get.user == user,
                              Get.get == get).\
                       first() is None:
                logger.debug("%s's %d GET", user.username, get)
                try:
                    update_scrobbles_for_user(user)
                    update_scrobbles_for_user(user)
                    user_plays_count = int(re.sub("[^0-9]", "",
                                                  BeautifulSoup(
                                                      requests.get(
                                                          "http://www.last.fm/ru/user/%s" % user.username
                                                      ).text
                                                  ).\
                                                  find("div", "header-metadata-global-stats").\
                                                  find("td", "metadata-display").\
                                                  text))
                except:
                    logger.error("Synchronizing error", exc_info=True)
                else:
                    session2 = db.create_scoped_session()
                    user2 = session2.query(User).get(user.id)

                    db_scrobbles = session2.query(func.count(Scrobble.id)).\
                                            filter(Scrobble.user == user2).\
                                            scalar()
                    logger.debug("user_plays_count = %s, db_scrobbles = %d", user_plays_count, db_scrobbles)

                    try:
                        scrobble = session2.query(Scrobble).\
                                            filter(Scrobble.user == user2).\
                                            order_by(Scrobble.uts)\
                                            [get - 1 - (user_plays_count - db_scrobbles)]
                    except:
                        logger.warning("There is no get yet", exc_info=True)
                    else:
                        g = Get()
                        g.user = user2
                        g.artist = scrobble.artist
                        g.artist_image = get_network().get_artist(scrobble.artist).get_cover_image()
                        g.track = scrobble.track
                        g.datetime = scrobble.datetime
                        g.get = get
                        session2.add(g)
                        session2.commit()

                        post_tweet(user, "%d GET: %s – %s!" % (g.get, g.artist, g.track.rstrip("!")))
