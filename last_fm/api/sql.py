# -*- coding: utf-8 -*-
from __future__ import absolute_import, division, unicode_literals

from flask import *
import ipaddress
import logging
import traceback

from last_fm.app import app
from last_fm.db import db

logger = logging.getLogger(__name__)


@app.route("/api/sql", methods=["POST"])
def sql():
    if not any(((ipaddress.ip_address(request.remote_addr.decode("ascii")) in ipaddress.ip_network(addr.decode("ascii")))
                if "/" in addr
                else (request.remote_addr == addr))
               for addr in app.config["SQL_API_CLIENTS"]):
        abort(403)

    try:
        return Response(json.dumps(map(dict, db.session.execute(request.json["query"], request.json["params"]))),
                        content_type="application/json")
    except:
        return Response(traceback.format_exc(), status=400, content_type="text/plain")
