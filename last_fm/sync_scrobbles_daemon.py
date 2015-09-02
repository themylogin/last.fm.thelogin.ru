# -*- coding: utf-8 -*-
from __future__ import absolute_import, unicode_literals

from collections import defaultdict
from datetime import datetime, timedelta
from flask import abort, Response
import json
import logging
from lxml import objectify
import socket
from sqlalchemy.sql import func
import threading
import time
import urllib
import urllib2

from themylog.client import setup_logging_handler
from themyutils.misc import retry

from last_fm.app import app
from last_fm.db import db
from last_fm.models import *

setup_logging_handler("last.fm_sync_scrobbles_daemon")

logger = logging.getLogger()

socket.setdefaulttimeout(10)


##     ## ########  ########     ###    ######## ########          ######   ######  ########   #######  ########  ########  ##       ########  ######  
##     ## ##     ## ##     ##   ## ##      ##    ##               ##    ## ##    ## ##     ## ##     ## ##     ## ##     ## ##       ##       ##    ## 
##     ## ##     ## ##     ##  ##   ##     ##    ##               ##       ##       ##     ## ##     ## ##     ## ##     ## ##       ##       ##       
##     ## ########  ##     ## ##     ##    ##    ######            ######  ##       ########  ##     ## ########  ########  ##       ######    ######  
##     ## ##        ##     ## #########    ##    ##                     ## ##       ##   ##   ##     ## ##     ## ##     ## ##       ##             ## 
##     ## ##        ##     ## ##     ##    ##    ##               ##    ## ##    ## ##    ##  ##     ## ##     ## ##     ## ##       ##       ##    ## 
 #######  ##        ########  ##     ##    ##    ########          ######   ######  ##     ##  #######  ########  ########  ######## ########  ######  


def get_recent_tracks(user, **kwargs):
    return retry(lambda: objectify.fromstring(
        urllib2.urlopen("http://ws.audioscrobbler.com/2.0/?" + urllib.urlencode(dict(method="user.getrecenttracks",
                                                                                     api_key=app.config["LAST_FM_API_KEY"],
                                                                                     user=user.username,
                                                                                     **kwargs))).read(),
        objectify.makeparser(encoding="utf-8", recover=True)
    ), logger=logger)


def count_xml_scrobbles(user, **kwargs):
    return int(get_recent_tracks(user, **kwargs).recenttracks.get("total"))


def format_uts(uts):
    return datetime.fromtimestamp(uts).strftime("%Y-%m-%d %H:%M:%S")


locks = defaultdict(threading.Lock)
def update_scrobbles(user, asap=False):
    with locks[user.username]:
        logger.debug("update_scrobbles('%s', asap=%r)", user.username, asap)

        session = db.create_scoped_session()

        total_db_scrobbles,\
        first_scrobble_uts,\
        last_scrobble_uts = session.query(func.count(Scrobble.id),
                                          func.min(Scrobble.uts),
                                          func.max(Scrobble.uts)).\
                                    filter(Scrobble.user == user).\
                                    first()

        delete_after = None
        if total_db_scrobbles > 0:
            download_from = last_scrobble_uts + 1

            if not asap:
                total_xml_scrobbles = count_xml_scrobbles(user, to=last_scrobble_uts + 1)
                if total_xml_scrobbles < total_db_scrobbles - 10:
                    logger.warning("User %s scrobble count decreased (%d -> %d), possible remote database corruption. "
                                   "Not removing", user.username, total_db_scrobbles, total_xml_scrobbles)
                elif total_xml_scrobbles != total_db_scrobbles:
                    logger.debug("User %s is not okay (has %d tracks, should have %d by %s)",
                                 user.username, total_db_scrobbles, total_xml_scrobbles, format_uts(last_scrobble_uts))

                    left = first_scrobble_uts
                    right = last_scrobble_uts
                    was_okay_at = 0
                    while abs(left - right) > 86400:
                        middle = left + (right - left) / 2

                        xml_scrobbles = count_xml_scrobbles(user, to=middle)
                        db_scrobbles = session.query(func.count(Scrobble.id)).\
                                               filter(Scrobble.user == user,
                                                      Scrobble.uts < middle).\
                                               scalar()

                        if db_scrobbles == xml_scrobbles:
                            logger.debug("User %s was okay before %s (scrobbles = %d)",
                                         user.username, format_uts(middle), db_scrobbles)
                            left = middle
                            was_okay_at = middle
                        else:
                            logger.debug("User %s was not okay before %s (db_scrobbles = %d, xml_scrobbles = %d)",
                                         user.username, format_uts(middle), db_scrobbles, xml_scrobbles)
                            right = middle

                    delete_after = min(left, right, was_okay_at)
                    download_from = delete_after
        else:
            download_from = 0

        to = ""
        page = 1
        pages = -1
        scrobbles = []
        got_track = False
        now_playing = None
        while pages == -1 or page <= pages:
            logger.debug("Opening %s's page %d of %d", user.username, page, pages)
            xml = get_recent_tracks(user, **{"from": download_from, "to": to, "page": page})

            if pages == -1:
                pages = int(xml.recenttracks.get("totalPages"))

            for track in xml.recenttracks.iter("track"):
                got_track = True
                try:
                    date = int(track.date.get("uts"))
                except Exception:
                    now_playing = {"artist": unicode(track.artist),
                                   "album": unicode(track.album),
                                   "track": unicode(track.name)}
                    continue

                if to == "":
                    to = str(date + 1)

                scrobbles.append(track)

            page = page + 1

        if delete_after is not None:
            count = session.query(Scrobble).\
                            filter(Scrobble.user == user,
                                   Scrobble.uts >= delete_after).\
                            delete()
            logger.info("Deleted %d scrobbles for %s", count, user.username)

        for xml_scrobble in reversed(scrobbles):
            session.execute(Scrobble.__table__.insert().values(
                user_id = user.id,
                artist  = unicode(xml_scrobble.artist),
                album   = unicode(xml_scrobble.album),
                track   = unicode(xml_scrobble.name),
                uts     = int(xml_scrobble.date.get("uts")),
            ))
        if len(scrobbles):
            logger.info("Inserted %d scrobbles for %s", len(scrobbles), user.username)

        session.commit()

        if not got_track and download_from != 0:
            xml = get_recent_tracks(user)

            for track in xml.recenttracks.iter("track"):
                try:
                    track.date.get("uts")
                except Exception:
                    now_playing = {"artist": unicode(track.artist),
                                   "album": unicode(track.album),
                                   "track": unicode(track.name)}

        return now_playing


##     ##    ###    #### ##    ##    ##        #######   #######  ########  
###   ###   ## ##    ##  ###   ##    ##       ##     ## ##     ## ##     ## 
#### ####  ##   ##   ##  ####  ##    ##       ##     ## ##     ## ##     ## 
## ### ## ##     ##  ##  ## ## ##    ##       ##     ## ##     ## ########  
##     ## #########  ##  ##  ####    ##       ##     ## ##     ## ##        
##     ## ##     ##  ##  ##   ###    ##       ##     ## ##     ## ##        
##     ## ##     ## #### ##    ##    ########  #######   #######  ##        


def main_loop():
    while True:
        update_started_at = time.time()

        try:
            users = db.create_scoped_session().query(User).filter(User.download_scrobbles == True).all()
        except Exception as e:
            logger.debug("Failed to query users", exc_info=True)

        for user in users:
            try:
                update_scrobbles(user)
            except Exception as e:
                logger.debug("Failed to update scrobbles for %s", user.username, exc_info=True)

        update_finished_at = time.time()

        next_update_in = 3600 - (update_finished_at - update_started_at)
        if next_update_in > 0:
            time.sleep(next_update_in)


##      ## ######## ########      ######  ######## ########  ##     ## ######## ########  
##  ##  ## ##       ##     ##    ##    ## ##       ##     ## ##     ## ##       ##     ## 
##  ##  ## ##       ##     ##    ##       ##       ##     ## ##     ## ##       ##     ## 
##  ##  ## ######   ########      ######  ######   ########  ##     ## ######   ########  
##  ##  ## ##       ##     ##          ## ##       ##   ##    ##   ##  ##       ##   ##   
##  ##  ## ##       ##     ##    ##    ## ##       ##    ##    ## ##   ##       ##    ##  
 ###  ###  ######## ########      ######  ######## ##     ##    ###    ######## ##     ## 


@app.route("/update_scrobbles/<username>")
def web_update_scrobbles(username):
    user = User.query.filter_by(username=username).first_or_404()
    try:
        return Response(json.dumps(update_scrobbles(user, asap=True)), headers={b"Content-type": b"application/json"})
    except Exception:
        logger.debug("Failed to update scrobbles on user request", exc_info=True)
        abort(500)


if __name__ == "__main__":
    main_loop_thread = threading.Thread(target=main_loop)
    main_loop_thread.daemon = True
    main_loop_thread.start()

    app.run(host="127.0.0.1", port=46400, threaded=True)
