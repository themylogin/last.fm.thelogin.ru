# -*- coding: utf-8 -*-
from __future__ import absolute_import, division, unicode_literals

import argparse
import logging
import mpd
import mutagen
import os
import pickle
import pipes
import random
import re
from sqlalchemy import func
import subprocess
import sys

from last_fm.db import db
from last_fm.models import Scrobble, User

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)


def get_directories(path):
    directories = subprocess.check_output("find %s -type d -printf \"%%T@\\t%%p\\n\" | sort | cut -f 2" %
                                          pipes.quote(path), shell=True).strip().split(b"\n")
    directories = filter(lambda x: not re.search("(CD|Disc)\s*\d", x), directories)
    return directories


def streq(s1, s2):
    s1l = s1.lower()
    s2l = s2.lower()
    return s1l.startswith(s2l) or s2l.startswith(s1l)


def user_by_username(username):
    user = db.session.query(User).filter_by(username=username).first()
    if user is not None:
        return user
    else:
        raise ValueError("User %s not found" % username)

if __name__ == "__main__":
    client = mpd.MPDClient()
    client.connect(os.getenv("MPD_HOST", "localhost"), int(os.getenv("MPD_PORT", "6600")))

    parser = argparse.ArgumentParser(description="last.fm mpd new music")
    parser.add_argument("path")
    parser.add_argument("user", type=user_by_username)
    parser.add_argument("--sort", choices=("random", "recent"), default="recent")
    parser.add_argument("--update-cache", action="store_true")
    args = parser.parse_args(sys.argv[1:])

    cache_path = "%s.cache" % __file__
    if not os.path.exists(cache_path) or args.update_cache:
        with open(cache_path, "w") as f:
            f.write(pickle.dumps(get_directories(args.path)))
        if args.update_cache:
            sys.exit(1)
    with open(cache_path, "r") as f:
        directories = pickle.loads(f.read())

    if args.sort == "random":
        random.shuffle(directories)
    else:
        directories = list(reversed(directories))

    for d in directories:
        files = sum([[os.path.join(root, file)
                      for file in files]
                     for root, dirs, files in os.walk(d)], [])
        files = filter(lambda x: any(x.endswith(ext) for ext in (b".flac", b".mp3")), files)
        if not (4 <= len(files) <= 30):
            logger.warning("%r len = %d" % (d, len(files)))
            continue

        for f in files:
            abs_filename = os.path.join(d, f)
            try:
                if os.path.splitext(f) == b".mp3":
                    metadata = mutagen.easyid3.EasyID3(abs_filename)
                else:
                    metadata = mutagen.File(abs_filename)

                if metadata is None:
                    continue
            except Exception:
                metadata = {}

            artist = metadata.get("artist", [None])[0]
            title = metadata.get("title", [None])[0]
            if artist and title:
                scrobble_count = db.session.query(func.count(Scrobble.id)).\
                                            filter(Scrobble.user == args.user,
                                                   Scrobble.artist == artist,
                                                   Scrobble.track == title).\
                                            scalar()
                if scrobble_count == 0:
                    client.add(os.path.relpath(d, args.path))
                    sys.exit(0)
                else:
                    logger.warning("%r — %r from %r was scrobbled %d time(s)" % (artist, title, d, scrobble_count))

                break
