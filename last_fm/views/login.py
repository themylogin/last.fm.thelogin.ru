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
from last_fm.utils.network import *


@app.route("/login")
def login():
    return redirect("%(homepage)s/api/auth?api_key=%(api)s&cb=%(callback_url)s" % {
        "homepage"      : network.homepage,
        "api"           : app.config["LAST_FM_API_KEY"],
        "callback_url"  : urlencode(url_for("login_callback", next=request.args.get("next"), _external=True)),
    })


@app.route("/login/callback")
def login_callback():
    req = pylast._Request(network, "auth.getSession", {"token": request.args.get("token")})
    req.sign_it()
    doc = req.execute()
    session_key = doc.getElementsByTagName("key")[0].firstChild.data
    username = doc.getElementsByTagName("name")[0].firstChild.data

    user = db.session.query(User).filter_by(username=username).first()
    if user is None:
        user = User()
        user.username = username
        
        db.session.add(user)

    user.session_key = session_key
    
    user.data = get_user_data(get_network(session_key=session_key, username=username).get_authenticated_user())
    user.data_updated = datetime.now()
    
    db.session.commit()

    login_user(user, remember=True)
    return redirect(request.args.get("next", url_for("index")))


@app.route("/logout")
@login_required
def logout():    
    logout_user()
    return redirect(url_for("index"))


@app.route("/impersonate/<username>")
@login_required
def impersonate(username):
    if not (current_user.id == 11 or session.get("allow_impersonation")):
        abort(403)

    login_user(db.session.query(User).filter(User.username == username).one(), remember=True)
    session["allow_impersonation"] = True
    return redirect(request.args.get("next", url_for("index")))
