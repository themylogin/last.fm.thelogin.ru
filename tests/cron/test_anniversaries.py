# -*- coding=utf-8 -*-
from __future__ import absolute_import, division, unicode_literals

from datetime import datetime, timedelta
import time

from mock import Mock, patch, ANY

from themyutils.flask.testing import FlaskIntegrationTestCase

from last_fm import app
from last_fm.cron.anniversaries import tweet_anniversaries
from last_fm.db import db
from last_fm.models import User, Scrobble, Artist, UserArtist


class TweetAnniversariesTestCase(FlaskIntegrationTestCase(app, db)):
    def setUp(self):
        super(TweetAnniversariesTestCase, self).setUp()

        user = User()
        user.download_scrobbles = True
        user.twitter_username = "themylogin"
        user.twitter_track_artist_anniversaries = True
        db.session.add(user)

        for i in range(1000):
            s = Scrobble()
            s.user = user
            s.artist = "God Is An Astronaut"
            s.track = "Track #%d" % i
            s.uts = time.mktime((datetime(2011, 1, 1, 0, 0, 0) + timedelta(days=i)).timetuple())
            db.session.add(s)

        a = Artist()
        a.name = "God Is An Astronaut"
        db.session.add(a)

        ua = UserArtist()
        ua.user = user
        ua.artist = a
        ua.scrobbles = 1000
        ua.first_real_scrobble = time.mktime(datetime(2011, 1, 1, 0, 0, 0).timetuple())
        db.session.add(ua)

        db.session.commit()

    @patch("last_fm.cron.anniversaries.datetime", Mock(now=Mock(return_value=datetime(2013, 12, 31, 23, 59, 55))))
    @patch("last_fm.cron.anniversaries.post_tweet")
    def test_no_anniversaries(self, post_tweet):
        tweet_anniversaries()
        post_tweet.assert_not_called()

    @patch("last_fm.cron.anniversaries.datetime", Mock(now=Mock(return_value=datetime(2014, 1, 1, 0, 0, 5))))
    @patch("last_fm.cron.anniversaries.post_tweet")
    def test_positive_anniversary(self, post_tweet):
        tweet_anniversaries()
        post_tweet.assert_called_once_with(ANY, "Уже 3 года слушаю God Is An Astronaut: Track #0!")

    @patch("last_fm.cron.anniversaries.datetime", Mock(now=Mock(return_value=datetime(2014, 9, 25, 23, 59, 55))))
    @patch("last_fm.cron.anniversaries.post_tweet")
    def test_no_positive_anniversary(self, post_tweet):
        tweet_anniversaries()
        post_tweet.assert_not_called()

    @patch("last_fm.cron.anniversaries.datetime", Mock(now=Mock(return_value=datetime(2014, 9, 26, 0, 0, 5))))
    @patch("last_fm.cron.anniversaries.post_tweet")
    def test_negative_anniversary(self, post_tweet):
        tweet_anniversaries()
        post_tweet.assert_called_once_with(ANY, "Уже год не слушал God Is An Astronaut: Track #999 :(")

    @patch("last_fm.cron.anniversaries.datetime", Mock(now=Mock(return_value=datetime(2015, 9, 26, 0, 0, 5))))
    @patch("last_fm.cron.anniversaries.post_tweet")
    def test_further_negative_anniversary(self, post_tweet):
        tweet_anniversaries()
        post_tweet.assert_called_once_with(ANY, "Уже 2 года не слушаю God Is An Astronaut: Track #999 :(")
