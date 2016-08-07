# -*- coding: utf-8 -*-
from __future__ import absolute_import, division, unicode_literals

from contextlib import closing
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.event import listens_for
from psycopg2.extensions import new_type, register_type

from last_fm.app import app

__all__ = [b"db"]

db = SQLAlchemy(app)


@listens_for(db.engine, "first_connect")
def register_citext_type(dbapi_con, connection_record):
    def cast_citext(in_str, cursor):
        if in_str == None:
            return None
        return unicode(in_str, cursor.connection.encoding)
    with closing(dbapi_con.cursor()) as c:
        c.execute(b"SELECT pg_type.oid FROM pg_type WHERE typname = 'citext'")
        citext_oid = c.fetchone()
        if citext_oid != None:
            citext_type = new_type(citext_oid, b"CITEXT", cast_citext)
            register_type(citext_type)
