# -*- coding: utf-8 -*-
from __future__ import absolute_import, unicode_literals

from datetime import datetime
from flask import *
from flask.ext.security import current_user, login_required
from flask_wtf import Form
import oauth2
import re
import twitter
import urllib
from urlparse import parse_qsl
from wtforms import fields, validators

from last_fm.api import ManageGuests
from last_fm.app import app
from last_fm.db import db
from last_fm.models import *
from last_fm.utils.twitter import get_api_for_user
from last_fm.utils import normalize_mac_address


@app.route("/usercp", methods=["GET", "POST"])
@login_required
def usercp():
    class DevicesListField(fields.TextAreaField):
        def process_formdata(self, valuelist):
            if valuelist:
                self.data = map(normalize_mac_address, filter(None, map(lambda s: s.strip(), valuelist[0].split("\n"))))
            else:
                self.data = []

        def pre_validate(self, form):
            for device in self.data:
                if not re.match(r"^[0-9a-f]{2}:[0-9a-f]{2}:[0-9a-f]{2}:[0-9a-f]{2}:[0-9a-f]{2}:[0-9a-f]{2}$", device):
                    raise ValueError("%s - это не MAC-адрес" % device)

        def _value(self):
            if self.data:
                return "\n".join(self.data)
            else:
                return ""

    class StopIfUnchecked(object):
        def __init__(self, boolean_field_name):
            self.boolean_field_name = boolean_field_name

        def __call__(self, form, field):
            if getattr(form, self.boolean_field_name).data == False:
                field.errors = []
                raise validators.StopValidation()

    class UsercpForm(Form):
        devices                     = DevicesListField(label="MAC-адреса ваших устройств для авторизации в умном доме")
        auto_add_devices            = fields.BooleanField(label="Автоматически добавлять адреса устройств, с которых вы заходите на сайт в умном доме")

        use_twitter_data            = fields.BooleanField(label="Использовать данные Twitter-аккаунта (@%s) для приветствия в умном доме" % current_user.twitter_username)

        twitter_track_repeats       = fields.BooleanField(label="Постить репиты в твиттер")
        twitter_repeats_min_count   = fields.IntegerField(label="Минимальное количество скробблов (от 5)", validators=[StopIfUnchecked("twitter_track_repeats"),
                                                                                                                       validators.NumberRange(min=5, message="Не меньше 5!")])
        twitter_post_repeat_start   = fields.BooleanField(label="Постить начало репита")

        twitter_track_artist_milestones     = fields.BooleanField(label="Постить ачивки скроббов исполнителей (666, 1000, 2000, ...)")

        twitter_win_artist_races            = fields.BooleanField(label="Участвовать в гонках исполнителей с друзьями")
        twitter_artist_races_min_count      = fields.IntegerField(label="Минимальное количество скробблов исполнителя (от 250)", validators=[StopIfUnchecked("twitter_win_artist_races"),
                                                                                                                                             validators.NumberRange(min=250, message="Не меньше 250!")])
        twitter_lose_artist_races           = fields.BooleanField(label="Постить, когда друг выигрывает меня в гонке")
 
        submit                      = fields.SubmitField(label="Сохранить")

    form = UsercpForm(obj=current_user)
    if form.validate_on_submit():
        form.populate_obj(current_user)
        db.session.commit()
        ManageGuests.notify_changes()
        return redirect(url_for("usercp"))
    else:
        return render_template("usercp.html", form=form)


@app.route("/usercp/twitter", methods=["GET"])
@login_required
def twitter_init():
    oauth_consumer  = oauth2.Consumer(key=app.config["TWITTER_CONSUMER_KEY"], secret=app.config["TWITTER_CONSUMER_SECRET"])
    oauth_client    = oauth2.Client(oauth_consumer)

    resp, content   = oauth_client.request(twitter.REQUEST_TOKEN_URL, "POST", body=urllib.urlencode({ "oauth_callback" : url_for("twitter_callback", _external=True) }))
    if resp["status"] != "200":
        raise Exception("Unable to request token from Twitter: %s" % resp["status"])
    session["twitter_oauth_data"] = dict(parse_qsl(content))
    
    return redirect(twitter.AUTHORIZATION_URL + "?oauth_token=" + session["twitter_oauth_data"]["oauth_token"])


@app.route("/usercp/twitter/callback")
def twitter_callback():    
    oauth_token = oauth2.Token(session["twitter_oauth_data"]["oauth_token"], session["twitter_oauth_data"]["oauth_token_secret"])
    oauth_token.set_verifier(request.args.get("oauth_verifier"))

    oauth_consumer  = oauth2.Consumer(key=app.config["TWITTER_CONSUMER_KEY"], secret=app.config["TWITTER_CONSUMER_SECRET"])
    oauth_client    = oauth2.Client(oauth_consumer, oauth_token)

    resp, content   = oauth_client.request(twitter.ACCESS_TOKEN_URL, "POST")
    oauth_data      = dict(parse_qsl(content))

    current_user.twitter_oauth_token        = oauth_data["oauth_token"]
    current_user.twitter_oauth_token_secret = oauth_data["oauth_token_secret"]

    current_user.twitter_data               = get_api_for_user(current_user).VerifyCredentials().AsDict()
    current_user.twitter_data_updated       = datetime.now()

    current_user.twitter_username           = current_user.twitter_data["screen_name"]

    db.session.commit()
    ManageGuests.notify_changes()

    return redirect(url_for("usercp"))
