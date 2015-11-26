# -*- coding: utf-8 -*-

import argparse
from datetime import datetime
import dateutil.parser
import mpd
from sqlalchemy import func
import os
import sys
import time

from last_fm.db import db
from last_fm.models import Scrobble, User


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

    parser = argparse.ArgumentParser(description="last.fm mpd random")
    parser.add_argument("user", action="append", nargs="+", type=user_by_username)
    parser.add_argument("--exclude-user", action="append", nargs="+", type=user_by_username)
    parser.add_argument("--limit", action="store", type=int, default=12 * 3600)
    parser.add_argument("--from", action="store", type=dateutil.parser.parse, default=datetime.min)
    parser.add_argument("--to", action="store", type=dateutil.parser.parse, default=datetime.max)
    parser.add_argument("--include-dir", action="append", nargs="+")
    parser.add_argument("--exclude-dir", action="append", nargs="+")
    parser.add_argument("--min-count", action="store", type=int, default=5)
    parser.add_argument("--max-length", action="store", type=int, default=600)
    args = parser.parse_args(sys.argv[1:])

    added = 0
    for artist, title in db.session.query(Scrobble.artist, Scrobble.track).\
                                    filter(
                                        Scrobble.user_id.in_([user.id for user in sum(args.user, [])]),
                                        Scrobble.uts >= time.mktime(getattr(args, "from").timetuple()),
                                        Scrobble.uts <= time.mktime(args.to.timetuple())
                                    ).\
                                    having(func.count(Scrobble.id) >= args.min_count).\
                                    group_by(Scrobble.artist, Scrobble.track).\
                                    order_by(func.rand()):
        if args.exclude_user:
            if db.session.query(func.count(Scrobble.id)).\
                          filter(
                              Scrobble.user_id.in_([user.id for user in sum(args.exclude_user, [])]),
                              Scrobble.artist == artist,
                              Scrobble.track == title
                          ).\
                          scalar() > 0:
                continue

        for track in client.find("title", title.encode("utf-8")):
            if "artist" not in track:
                continue
            if isinstance(track["artist"], list):
                track["artist"] = track["artist"][0]

            if "title" not in track:
                continue
            if isinstance(track["title"], list):
                track["title"] = track["title"][0]

            if streq(artist, track["artist"].decode("utf-8")) and streq(title, track["title"].decode("utf-8")):
                include = True
                if args.include_dir:
                    include = False
                    for d in sum(args.include_dir, []):
                        if track["file"].startswith(d):
                            include = True
                            break
                if not include:
                    continue

                exclude = False
                if args.exclude_dir:
                    for d in sum(args.exclude_dir, []):
                        if track["file"].startswith(d):
                            exclude = True
                            break
                if exclude:
                    continue

                if int(track["time"]) > args.max_length:
                    continue

                client.add(track["file"])
                added += int(track["time"])
                break

        if added >= args.limit:
            break
