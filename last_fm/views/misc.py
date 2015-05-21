# -*- coding=utf-8 -*-
from __future__ import absolute_import, division, unicode_literals

from datetime import datetime
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


@app.route("/gets")
@login_required
def gets():
    bbcode = '[align=center][quote][size=15][b]Last.FM Milestones[/b][/size][b][color=black]'
    for get in db.session.query(Get).\
                          filter(Get.user == current_user).\
                          order_by(Get.get):
        bbcode += "[quote]%dth track: (%s)\n" % (get.get, get.datetime.strftime("%d %b %Y"))
        bbcode += "[artist]%s[/artist] - [track artist=%s]%s[/track]" % (get.artist, get.artist, get.track)
        bbcode += "[img]%s[/img][/quote]" % (get.artist_image.replace("/_/", "/252/"))
    bbcode += "[color=navy]Generated on %s[/color]\n" % datetime.now().strftime("%d %b %Y")
    bbcode += "[color=navy]Get yours [b][url=http://kastuvas.us.to/lastfm/]here[/url][/b][/color][/quote][/color][/b][/quote][/align]"
    return render_template("gets.html", bbcode=bbcode)
