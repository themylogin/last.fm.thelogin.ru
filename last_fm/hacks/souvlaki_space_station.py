# -*- coding=utf-8 -*-
from __future__ import absolute_import, unicode_literals

from flask import *
from flask.ext.login import current_user
import json
import logging
import urllib2

from last_fm.app import app
from last_fm.api.guests import ManageGuests
from last_fm.db import db

logger = logging.getLogger(__name__)

if app.config.get("GUESTS_DEVICES_RESOLVER"):
    def update_user_devices_for_local_request():
        if current_user.is_authenticated():
            if current_user.auto_add_devices:
                if any(request.remote_addr.startswith(prefix)
                       for prefix in app.config["GUESTS_DEVICES_PREFIXES"]):
                    device = None
                    try:
                        device = json.loads(urllib2.urlopen("%s/ip/%s" % (app.config["GUESTS_DEVICES_RESOLVER"],
                                                                          request.remote_addr)).read())
                    except urllib2.HTTPError as e:
                        if e.code != 404:
                            raise
                    except:
                        logging.exception("Exception while communicating with guests device resolver")

                    if device:
                        if device not in current_user.devices:
                            current_user.devices = current_user.devices + [device]
                            db.session.commit()

                            if not ManageGuests.get_current_visit(current_user):
                                ManageGuests.create_visit(current_user, {"device": device})

    app.before_request(update_user_devices_for_local_request)
