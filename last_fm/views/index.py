# -*- coding: utf-8 -*-
from __future__ import absolute_import, division, unicode_literals

from datetime import datetime
from flask import *
from flask.ext.security import current_user, login_required
from lxml.html.soupparser import fromstring
from lxml.etree import tostring
import PyRSS2Gen
import StringIO

from last_fm.app import app
from last_fm.db import db
from last_fm.models import *


def get_releases_for(user):
    return db.session.query(UserRelease).\
                      join(Release).\
                      filter(UserRelease.user == user).\
                      filter(~UserRelease.artist.in_(get_ignored_artists_for(user))).\
                      order_by(Release.id.desc())


def get_ignored_artists_for(user):
    return [a for (a,) in db.session.query(UserArtistIgnore.artist).filter(UserArtistIgnore.user == user)]


def get_release_html(release):
    try:
        tree = fromstring(release.content)
        for img in tree.xpath("//img"):
            img.attrib["src"] = "http://last.fm.thelogin.ru/static/covers/%s" % img.attrib["src"].replace("://", "/")
        return tostring(tree, pretty_print=True, encoding="utf-8").decode("utf-8").\
                                                                   replace("<html>", "").\
                                                                   replace("</html>", "")
    except Exception:
        return release.content


@app.route("/")
def index():
    if current_user.is_authenticated:
        return render_template("index.html", releases=get_releases_for(current_user),
                                             get_release_html=get_release_html)
    else:
        return render_template("jumbotron.html")


@app.route("/rss/<username>")
def rss(username):
    user = db.session.query(User).filter(User.username == username).first()
    if user is None:
        abort(404)

    rss = PyRSS2Gen.RSS2(
        title           =   "%(user)s - last.fm.thelogin.ru" % \
                            {
                                "user"  :   user.username,
                            },
        link            =   url_for("rss", username=user.username),
        description     =   "",
        lastBuildDate   =   datetime.now(),
        items           =   [
                                PyRSS2Gen.RSSItem(
                                    title       = user_release.release.title,
                                    link        = user_release.release.url,
                                    description = get_release_html(user_release.release),
                                    guid        = PyRSS2Gen.Guid(user_release.release.url),
                                    pubDate     = user_release.release.date
                                )
                                for user_release in get_releases_for(user)
                            ]
    )
    rss_string = StringIO.StringIO()
    rss.write_xml(rss_string, "utf-8")

    return Response(rss_string.getvalue(), content_type="text/xml")


@app.route("/ignore-artist", methods=["POST"])
@login_required
def ignore_artist():
    ignore = UserArtistIgnore()
    ignore.user = current_user
    ignore.artist = request.form.get("artist")
    db.session.add(ignore)
    db.session.commit()
    
    return jsonify([])
