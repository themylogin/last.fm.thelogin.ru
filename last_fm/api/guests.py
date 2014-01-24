# -*- coding: utf-8 -*-
from __future__ import absolute_import, unicode_literals

from datetime import datetime
from flask import *
from flask.ext import restful
from redis import Redis

from last_fm.app import app
from last_fm.db import db
from last_fm.models import *
from last_fm.utils import normalize_mac_address

version_key = "last.fm:guests_api:guests_version"
version_pubsub_key = "last.fm:guests_api:guests_version_pubsub"

Redis().incr(version_key)


def prepare_user(user):
    data = {
        "api_key":      app.config["LAST_FM_API_KEY"],
        "api_secret":   app.config["LAST_FM_API_SECRET"],

        "id":           user.id,
        "username":     user.username,
        "session_key":  user.session_key,

        "visits":       [prepare_visit(visit)
                         for visit in db.session.query(GuestVisit).\
                                                 filter(GuestVisit.user == user,
                                                        GuestVisit.left != None).\
                                                 order_by(GuestVisit.came)],
    }
    if user.use_twitter_data:
        data["title"] = user.twitter_username
        data["avatar"] = user.twitter_data.get("profile_image_url")
    else:
        data["title"] = user.username
        data["avatar"] = user.data.get("image", "http://cdn.last.fm/flatness/responsive/2/noimage/default_user_140_g2.png")
    return data


def prepare_visit(visit):
    data = {}
    data["came"] = {
        "at":   visit.came.isoformat(),
        "data": visit.came_data,
    }
    if visit.left is not None:
        data["left"] = {
            "at":   visit.left.isoformat(),
            "data": visit.left_data,
        }
    return data


class Users(restful.Resource):
    def get(self):
        users = []
        for user in db.session.query(User).\
                               filter(User.session_key != None).\
                               order_by(User.username):
            current_visit = ManageGuests.get_current_visit(user)
            users.append({
                "user": prepare_user(user),
                "came": prepare_visit(current_visit)["came"] if current_visit else False,
            })

        return users


class UserByDevice(restful.Resource):
    def get(self, device):
        for user in db.session.query(User).all():
            if normalize_mac_address(device) in user.devices:
                return prepare_user(user)

        abort(404)


class Guests(restful.Resource):
    def get(self):
        range_header = request.headers.get("Range", None)
        if range_header:
            try:
                client_version = int(range_header.split("-")[0])
            except:
                abort(400)

            redis = Redis()
            pubsub = redis.pubsub()
            pubsub.subscribe([version_pubsub_key])
            server_version = int(redis.get(version_key))
            if server_version == client_version:
                for item in pubsub.listen():
                    if item["type"] == "message":
                        break
        
        version = int(Redis().get(version_key))
        return {
            "version":  version,
            "guests":   [
                {
                    "user":     prepare_user(user),
                    "came":     prepare_visit(current_visit)["came"],
                }
                for current_visit, user in map(lambda visit: (visit, visit.user), db.session.query(GuestVisit).filter_by(left=None))
            ]
        }


class ManageGuests(restful.Resource):
    def post(self, user_id):
        user = self._get_user(user_id)
        current_visit = self.get_current_visit(user)
        if current_visit is not None:
            abort(403)

        self.create_visit(user, dict(request.form.items()))

    def delete(self, user_id):
        user = self._get_user(user_id)
        current_visit = self.get_current_visit(user)
        if current_visit is None:
            abort(403)

        current_visit.left = datetime.now()
        current_visit.left_data = dict(request.form.items())
        db.session.commit()

        self.notify_changes()

    def _get_user(self, user_id):
        user = db.session.query(User).get(user_id)
        if user is None:
            abort(404)

        return user

    @classmethod
    def get_current_visit(cls, user):
        return db.session.query(GuestVisit).filter_by(user=user, left=None).first()

    @classmethod
    def create_visit(cls, user, came_data):        
        visit = GuestVisit()
        visit.user = user
        visit.came = datetime.now()
        visit.came_data = came_data
        db.session.add(visit)
        db.session.commit()

        cls.notify_changes()

    @classmethod
    def notify_changes(cls):
        redis = Redis()
        redis.incr(version_key)
        redis.publish(version_pubsub_key, "")
