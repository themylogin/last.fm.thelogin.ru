# -*- coding: utf-8 -*-
from __future__ import absolute_import, unicode_literals

from flask.ext.script import Manager
import os
import subprocess
from urlparse import urlparse

from themyutils.sqlalchemy.sql import literal_query

from last_fm import app
from last_fm.db import db
from last_fm.cron.utils import jobs
from last_fm.models import *

manager = Manager(app)

@manager.command
def cron(job):
    app.debug = True
    jobs["last_fm.cron.%s" % job]()


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
