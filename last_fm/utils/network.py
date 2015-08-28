# -*- coding: utf-8 -*-
from __future__ import absolute_import, division, unicode_literals

import pylast

from last_fm.app import app

__all__ = [b"get_network", b"get_user_data"]


def get_network(*args, **kwargs):
    return pylast.get_lastfm_network(app.config["LAST_FM_API_KEY"], app.config["LAST_FM_API_SECRET"], *args, **kwargs)


def get_user_data(authenticated_user):
    data = {}
    for k in authenticated_user._request("user.getInfo", True).getElementsByTagName('*'):
        if k.firstChild and k.firstChild.nodeValue and k.firstChild.nodeValue.strip() != "":
            data[k.tagName] = k.firstChild.nodeValue
    return data
