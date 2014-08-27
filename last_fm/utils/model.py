# -*- coding: utf-8 -*-
from __future__ import absolute_import, division, unicode_literals

from sqlalchemy.sql import func

from last_fm.db import db
from last_fm.models import *


def get_user_artists(user, min_scrobbles=0):
    if user.download_scrobbles:
        return db.session.query(Scrobble.artist, func.count(Scrobble.id)).\
                          filter(Scrobble.user == user).\
                          having(func.count(Scrobble.id) >= min_scrobbles).\
                          group_by(Scrobble.artist)
    else:
        return db.session.query(UserArtist.artist, UserArtist.scrobbles).\
                          filter(UserArtist.user == user,
                                 UserArtist.scrobbles >= min_scrobbles)
