# -*- coding: utf-8 -*-
from __future__ import absolute_import, division, unicode_literals

from datetime import datetime
from flask import *
from flask.ext.login import current_user, login_required, login_user, logout_user
import pylast

from last_fm.app import app
from last_fm.db import db
from last_fm.models import *
from last_fm.network import network
from last_fm.utils import urlencode
from last_fm.utils.network import get_user_data


@app.route("/login")
def login():
    return redirect("%(homepage)s/api/auth/?api_key=%(api)s&cb=%(callback_url)s" % {
        "homepage"      : network.homepage,
        "api"           : app.config["LAST_FM_API_KEY"],
        "callback_url"  : urlencode(url_for("login_callback", next=request.args.get("next"), _external=True)),
    })


@app.route("/login/callback")
def login_callback():
    session_key_generator = pylast.SessionKeyGenerator(network)
    session_key_generator.web_auth_tokens["fake"] = request.args.get("token")
    session_key = session_key_generator.get_web_auth_session_key("fake")

    last_fm_user = pylast.get_lastfm_network(app.config["LAST_FM_API_KEY"],
                                             app.config["LAST_FM_API_SECRET"],
                                             session_key=session_key).get_authenticated_user()

    user = db.session.query(User).filter_by(username=last_fm_user.get_name()).first()
    if user is None:
        user = User()
        user.username = last_fm_user.get_name()
        
        db.session.add(user)

    user.session_key = session_key
    
    user.data = get_user_data(last_fm_user)
    user.data_updated = datetime.now()
    
    db.session.commit()

    login_user(user, remember=True)
    return redirect(request.args.get("next", url_for("index")))


@app.route("/logout")
@login_required
def logout():    
    logout_user()
    return redirect(url_for("index"))
