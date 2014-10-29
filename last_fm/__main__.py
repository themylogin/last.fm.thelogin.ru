# -*- coding: utf-8 -*-
from __future__ import absolute_import, division, unicode_literals

from datetime import datetime
import operator
import os
import subprocess
from texttable import Texttable
from urlparse import urlparse

from themyutils.sqlalchemy.sql import literal_query

from last_fm import app
from last_fm.analytics import calculate_first_real_scrobble
from last_fm.celery import cron as c
from last_fm.db import db
from last_fm.manager import manager
from last_fm.models import *


@manager.command
def cron(job):
    app.debug = True
    c.jobs["last_fm.cron.%s" % job]()


@manager.command
def debug_first_real_scrobble(user_id, min_scrobbles=250):
    user = db.session.query(User).get(user_id)
    user_artists = list(db.session.query(UserArtist).\
                                   join(Artist).\
                                   filter(UserArtist.user == user,
                                          UserArtist.scrobbles >= min_scrobbles,
                                          UserArtist.first_real_scrobble != None,
                                          UserArtist.first_real_scrobble_corrected != None).\
                                   order_by(Artist.name))

    new_first_real_scrobble = {}
    for i, user_artist in enumerate(user_artists):
        artist = user_artist.artist.name
        print "%s (%d / %d)" % (artist, i + 1, len(user_artists))
        new_first_real_scrobble[artist] = calculate_first_real_scrobble(db.session, user, artist).uts

    sections = [("Still broken", lambda user_artist, new_first_real_scrobble:\
                    (user_artist.first_real_scrobble != user_artist.first_real_scrobble_corrected and
                     new_first_real_scrobble != user_artist.first_real_scrobble_corrected and
                     new_first_real_scrobble == user_artist.first_real_scrobble)),
                ("Still broken, but changed", lambda user_artist, new_first_real_scrobble:
                    (user_artist.first_real_scrobble != user_artist.first_real_scrobble_corrected and
                     new_first_real_scrobble != user_artist.first_real_scrobble_corrected and
                     new_first_real_scrobble != user_artist.first_real_scrobble)),
                ("Newly broken", lambda user_artist, new_first_real_scrobble:
                    (user_artist.first_real_scrobble == user_artist.first_real_scrobble_corrected and
                     new_first_real_scrobble != user_artist.first_real_scrobble_corrected)),
                ("Fixed", lambda user_artist, new_first_real_scrobble:
                    (user_artist.first_real_scrobble != user_artist.first_real_scrobble_corrected and
                     new_first_real_scrobble == user_artist.first_real_scrobble_corrected))]
    for title, condition in sections:
        has_rows = False
        table = Texttable()
        table.header(["Artist", "Real", "Old", "New"])
        for user_artist in user_artists:
            artist = user_artist.artist.name
            if condition(user_artist, new_first_real_scrobble[artist]):
                has_rows = True
                table.add_row([artist.encode("utf-8")] +\
                              map(lambda uts: datetime.fromtimestamp(uts).strftime("%Y-%m-%d %H:%M"),
                                  [user_artist.first_real_scrobble_corrected,
                                   user_artist.first_real_scrobble,
                                   new_first_real_scrobble[artist]]))
        if has_rows:
            print "\n%s" % title
            print table.draw()

    if raw_input("Apply this? (y/n)") == "y":
        for user_artist in user_artists:
            user_artist.first_real_scrobble = new_first_real_scrobble[user_artist.artist.name]
    db.session.commit()


@manager.command
def dump_db_wo_sensitive_data():
    base_filename = os.path.join(app.static_folder, "dump.sql")
    db_config = urlparse(app.config["SQLALCHEMY_DATABASE_URI"])
    db_name = db_config.path[1:]

    if db_config.scheme == "mysql":
        dump = open(base_filename, "w+")

        subprocess.check_call(filter(None, [
            "mysqldump",
            "-h" + db_config.hostname,
            "-u" + db_config.username,
            "-p" + db_config.password if db_config.password else None,
            "--ignore-table=%s.%s" % (db_name, User.__tablename__),
            db_name,
        ]), stdout=dump)

        subprocess.check_call(filter(None, [
            "mysqldump",
            "-h" + db_config.hostname,
            "-u" + db_config.username,
            "-p" + db_config.password if db_config.password else None,
            "--no-data",
            db_name,
            User.__tablename__,
        ]), stdout=dump)

        for user in db.session.execute(User.__table__.select()):
            row = dict(user)
            for sensitive_key in ["session_key", "devices", "twitter_oauth_token", "twitter_oauth_token_secret"]:
                row[sensitive_key] = None
            dump.write(literal_query(User.__table__.insert(values=row), db.engine) + ";\n")

        dump.close()

        subprocess.check_call([
            "gzip", "-f",
            "--suffix", ".tmp",
            base_filename,
        ])

        if os.path.isfile(base_filename):
            os.unlink(base_filename)
        os.rename(base_filename + ".tmp", base_filename + ".gz")
    else:
        raise Exception("Dumping %s is not supported yet" % db_config.scheme)


if __name__ == "__main__":
    manager.run()
