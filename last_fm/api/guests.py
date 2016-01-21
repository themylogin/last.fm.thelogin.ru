# -*- coding: utf-8 -*-
from __future__ import absolute_import, division, unicode_literals

from datetime import datetime
from flask import *
from flask.ext.restful import abort, Resource
import gevent
from geventwebsocket import WebSocketError

from last_fm.app import app
from last_fm.db import db
from last_fm.models import *
from last_fm.utils import normalize_mac_address

__all__ = [b"Users", b"UserByDevice", b"Guests", b"ManageGuests"]

guest_asyncs = set()


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


class Users(Resource):
    def get(self):
        users = []
        for user in db.session.query(User).\
                               filter(User.session_key != None):
            current_visit = ManageGuests.get_current_visit(user)
            users.append({
                "user": prepare_user(user),
                "came": prepare_visit(current_visit)["came"] if current_visit else False,
            })

        return sorted(users, key=lambda user: user["user"]["title"].lower())


class UserByDevice(Resource):
    def get(self, device):
        for user in db.session.query(User).all():
            if normalize_mac_address(device) in user.devices:
                return prepare_user(user)

        abort(404)


class Guests(Resource):
    def get(self):
        if "wsgi.websocket" in request.environ:
            async = gevent.get_hub().loop.async()
            async.start(lambda: None)

            guest_asyncs.add(async)

            ws = request.environ["wsgi.websocket"]

            try:
                ws.send(self.dump_guests())

                while True:
                    gevent.get_hub().wait(async)
                    ws.send(self.dump_guests())
            except WebSocketError:
                pass
            finally:
                guest_asyncs.remove(async)

                if not ws.closed:
                    ws.close()

            return Response()
        else:
            return Response(self.dump_guests(), mimetype="application/json")

    def dump_guests(self):
        guests = json.dumps({
            "guests":   [
                {
                    "user":     prepare_user(user),
                    "came":     prepare_visit(current_visit)["came"],
                }
                for current_visit, user in map(lambda visit: (visit, visit.user),
                                               db.session.query(GuestVisit).filter_by(left=None))
            ]
        })
        db.session.close()
        return guests


class ManageGuests(Resource):
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
        for async in guest_asyncs.copy():
            async.send()
