# -*- coding=utf-8 -*-
from __future__ import absolute_import, division, unicode_literals

from flask import *
from flask.ext.security import current_user, login_required

from last_fm.analytics import find_day2scrobbles, find_day2scrobbles_gaps, find_first_scrobble_by_first_scrobble_appx
from last_fm.app import app
from last_fm.cache import cache
from last_fm.db import db
from last_fm.models import *


@app.route("/first_real_scrobble_corrected", methods=["GET", "POST"])
@login_required
def first_real_scrobble_corrected():
    if request.method == "POST":
        user_artist = db.session.query(UserArtist).\
                                 filter(UserArtist.user == current_user,
                                        UserArtist.id == request.form.get("artist", type=int)).\
                                 one()
        user_artist.first_real_scrobble_corrected = request.form.get("uts", type=int)
        db.session.commit()

        return redirect("first_real_scrobble_corrected")

    artist = db.session.query(UserArtist).\
                        filter(UserArtist.user == current_user,
                               UserArtist.scrobbles >= 250,
                               UserArtist.first_real_scrobble != None,
                               UserArtist.first_real_scrobble_corrected == None).\
                        order_by(UserArtist.scrobbles.desc()).\
                        first()
    scrobbles = db.session.query(Scrobble).\
                           filter(Scrobble.user == current_user,
                                  Scrobble.artist == artist.artist.name).\
                           order_by(Scrobble.uts) if artist else []

    return render_template("first_real_scrobble_corrected.html", artist=artist, scrobbles=scrobbles)
