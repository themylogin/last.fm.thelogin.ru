# -*- coding=utf-8 -*-
from __future__ import absolute_import, division, unicode_literals

import logging
import mpd

from last_fm.app import app

logger = logging.getLogger(__name__)

__all__ = [b"get_mpd"]


def get_mpd():
    client = mpd.MPDClient()
    client.connect(app.config["MPD_HOST"], 6600)
    return client
