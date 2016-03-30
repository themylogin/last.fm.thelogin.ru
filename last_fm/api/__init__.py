# -*- coding: utf-8 -*-
from __future__ import absolute_import, division, unicode_literals

from flask.ext import restful

from last_fm.app import app
from last_fm.api.guests import *

api = restful.Api(app)
api.add_resource(Users, "/users")
api.add_resource(UserByDevice, "/users/by-device/<device>")
api.add_resource(Guests, "/guests")
api.add_resource(ManageGuests, "/guests/<int:user_id>")

import last_fm.api.recommendations
import last_fm.api.sql
