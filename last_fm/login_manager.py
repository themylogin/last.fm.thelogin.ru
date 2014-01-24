# -*- coding: utf-8 -*-
from __future__ import absolute_import, unicode_literals

from flask.ext.login import LoginManager

from last_fm.db import db
from last_fm.models import User

login_manager = LoginManager()

login_manager.login_view = "login"


@login_manager.user_loader
def load_user(user_id):
    return db.session.query(User).get(user_id)
