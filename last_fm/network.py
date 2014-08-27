# -*- coding: utf-8 -*-
from __future__ import absolute_import, division, unicode_literals

import pylast

from last_fm.app import app

__all__ = [b"network"]

network = pylast.LastFMNetwork(app.config["LAST_FM_API_KEY"], app.config["LAST_FM_API_SECRET"])
