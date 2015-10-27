# -*- coding: utf-8 -*-
from __future__ import absolute_import, division, unicode_literals

from sqlalchemy.sql import func
import urllib2

from last_fm.db import db
from last_fm.models import *

__all__ = [b"get_artist", b"get_user_artists", b"update_scrobbles_for_user"]


def get_artist(artist_name, commit=True):
    artist = db.session.query(Artist).filter(Artist.name == artist_name).first()
    if artist is None:
        artist = Artist()
        artist.name = artist_name
        db.session.add(artist)
        if commit:
            db.session.commit()
    return artist


def get_user_artists(user, min_scrobbles=0):
    if user.download_scrobbles:
        return db.session.query(Scrobble.artist, func.count(Scrobble.id)).\
                          filter(Scrobble.user == user).\
                          having(func.count(Scrobble.id) >= min_scrobbles).\
                          group_by(Scrobble.artist)
    else:
        return db.session.query(Artist.name, UserArtist.scrobbles).\
                          join(UserArtist).\
                          filter(UserArtist.user == user,
                                 UserArtist.scrobbles >= min_scrobbles)


def update_scrobbles_for_user(user):
    urllib2.urlopen("http://127.0.0.1:46400/update_scrobbles/%s" % user.username).read()
