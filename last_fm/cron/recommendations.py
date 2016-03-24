# -*- coding=utf-8 -*-
from __future__ import absolute_import, division, unicode_literals

import logging
import pickle
import pipes
import re
import subprocess

from last_fm.celery import cron
import last_fm.config

logger = logging.getLogger(__name__)

__all__ = [b"update_mpd_music_directory_cache"]


def get_directories(path):
    directories = subprocess.check_output("find %s -type d -printf \"%%T@\\t%%p\\n\" | sort | cut -f 2" %
                                          pipes.quote(path), shell=True).strip().split(b"\n")
    directories = filter(lambda x: not re.search("(CD|Disc)\s*\d", x), directories)
    return directories


@cron.job(hour="*", minute=15)
def update_mpd_music_directory_cache():
    with open(last_fm.config.MPD_MUSIC_DIRECTORY_CACHE_PATH, "w") as f:
        f.write(pickle.dumps(get_directories(last_fm.config.MPD_MUSIC_DIRECTORY)))
