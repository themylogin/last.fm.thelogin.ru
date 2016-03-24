# -*- coding=utf-8 -*-
from __future__ import absolute_import, division, unicode_literals

import logging
import mpd

import last_fm.config

logger = logging.getLogger(__name__)

__all__ = [b"get_mpd"]


def get_mpd():
    client = mpd.MPDClient()
    client.connect(last_fm.config.MPD_HOST, 6600)
    return client
