# -*- coding: utf-8 -*-
from __future__ import absolute_import, division, unicode_literals

from datetime import datetime
import dateutil.parser
from flask import *
import logging
import mutagen
import mutagen.easyid3
import os
import pickle
import random
from sqlalchemy.sql import func
import time

from last_fm.app import app
import last_fm.config
from last_fm.db import db
from last_fm.models import *
from last_fm.utils.mpd import get_mpd
from last_fm.utils.string import streq

logger = logging.getLogger(__name__)


@app.route("/recommendations/<provider>/<username>")
def recommendations(provider, username):
    user = db.session.query(User).filter(User.username == username).one()
    recommendations = {"new": new_recommendations,
                       "familiar": familiar_recommendations}[provider](user)

    action = request.args.get("action", "print")
    if action == "print":
        return jsonify({"recommendations": list(recommendations)})
    elif action == "stream":
        return Response(stream_with_context(stream_recommendations(recommendations)))
    elif action == "mpd-add":
        mpd = get_mpd()
        for recommendation in recommendations:
            mpd.add(recommendation)
        return Response()
    else:
        abort(400)


def new_recommendations(user):
    exclude = request.args.getlist("exclude")
    sort = request.args.get("sort", "recent")
    limit = request.args.get("limit", 1, type=int)

    with open(last_fm.config.MPD_MUSIC_DIRECTORY_CACHE_PATH, "r") as f:
        directories = pickle.loads(f.read())

    if exclude:
        directories = filter(lambda d: not any(os.path.relpath(d, last_fm.config.MPD_MUSIC_DIRECTORY).startswith(e)
                                               for e in exclude),
                             directories)

    if sort == "recent":
        directories = list(reversed(directories))
    else:
        random.shuffle(directories)

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
                if os.path.splitext(f)[1].lower()[1:] == b"mp3":
                    metadata = mutagen.easyid3.EasyID3(abs_filename)
                else:
                    metadata = mutagen.File(abs_filename)

                if metadata is None:
                    logger.warning("Unable to read metadata from %r", abs_filename)
                    continue
            except Exception:
                logger.warning("Exception while reading metadata from %r", abs_filename)
                continue

            artist = metadata.get("artist", [None])[0]
            title = metadata.get("title", [None])[0]
            if artist and title:
                scrobble_count = db.session.query(func.count(Scrobble.id)).\
                                            filter(Scrobble.user == user,
                                                   Scrobble.artist == artist,
                                                   Scrobble.track == title).\
                                            scalar()
                if scrobble_count == 0:
                    yield os.path.relpath(d, last_fm.config.MPD_MUSIC_DIRECTORY)

                    limit -= 1
                    if limit == 0:
                        return
                else:
                    logger.warning("%r — %r from %r was scrobbled %d time(s)" % (artist, title, d, scrobble_count))

                break


def familiar_recommendations(user):
    exclude_users = [u[0] for u in db.session.query(User.id).\
                                        filter(User.username.in_(request.args.getlist("exclude-user")))]
    limit = request.args.get("limit", 12 * 3600, type=int)
    from_ = request.args.get("from", datetime.min, type=dateutil.parser.parse)
    to_ = request.args.get("from", datetime.max, type=dateutil.parser.parse)
    include_dirs = request.args.getlist("include-dir")
    exclude_dirs = request.args.getlist("exclude-dir")
    min_count = request.args.get("min-count", 5, type=int)
    max_length = request.args.get("max-length", 600, type=int)

    client = get_mpd()

    added = 0
    for artist, title in db.session.query(Scrobble.artist, Scrobble.track).\
                                    filter(
                                        Scrobble.user == user,
                                        Scrobble.uts >= time.mktime(from_.timetuple()),
                                        Scrobble.uts <= time.mktime(to_.timetuple())
                                    ).\
                                    having(func.count(Scrobble.id) >= min_count).\
                                    group_by(Scrobble.artist, Scrobble.track).\
                                    order_by(func.rand()):
        if exclude_users:
            if db.session.query(func.count(Scrobble.id)).\
                          filter(
                              Scrobble.user_id.in_(exclude_users),
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
                if include_dirs:
                    include = False
                    for d in include_dirs:
                        if track["file"].startswith(d):
                            include = True
                            break
                if not include:
                    continue

                exclude = False
                if exclude_dirs:
                    for d in exclude_dirs:
                        if track["file"].startswith(d):
                            exclude = True
                            break
                if exclude:
                    continue

                if int(track["time"]) > max_length:
                    continue

                yield track["file"]
                added += int(track["time"])
                break

        if added >= limit:
            break


def stream_recommendations(recommendations):
    for r in recommendations:
        yield b"%s\n" % r
