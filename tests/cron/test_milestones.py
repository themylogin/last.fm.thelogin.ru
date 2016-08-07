# -*- coding=utf-8 -*-
from __future__ import absolute_import, division, unicode_literals

from datetime import datetime, timedelta
from mock import Mock, call, patch
import time
import unittest

from themyutils.flask.testing import FlaskIntegrationTestCase

from last_fm import app
from last_fm.cron.milestones import tweet_milestones, chart_change_tweet
from last_fm.db import db
from last_fm.models import User, Scrobble


class ArtistRaceTweetTestCase(FlaskIntegrationTestCase(app, db)):
    @patch("last_fm.cron.milestones.post_tweet")
    @patch("last_fm.cron.milestones.update_scrobbles_for_user")
    @patch("last_fm.cron.milestones.get_api_for_user")
    def test_equal_scrobble_count_and_one_moves_forward(self, get_api_for_user, update_scrobbles_for_user, post_tweet):
        get_api_for_user.return_value = Mock(GetFriendIDs=Mock(return_value=[1, 2]))

        themylogin = User()
        themylogin.download_scrobbles = True
        themylogin.twitter_username = "themylogin"
        themylogin.twitter_data = {"id": 1}
        themylogin.twitter_win_artist_races = True
        themylogin.twitter_lose_artist_races = True
        db.session.add(themylogin)

        mutantcornholio = User()
        mutantcornholio.download_scrobbles = True
        mutantcornholio.twitter_username = "mutantcornholio"
        mutantcornholio.twitter_data = {"id": 2}
        mutantcornholio.twitter_win_artist_races = True
        mutantcornholio.twitter_lose_artist_races = True
        db.session.add(mutantcornholio)

        for i in range(404):
            s = Scrobble()
            s.user = themylogin
            s.artist = "Burial"
            s.track = "Track #%d" % i
            s.uts = time.mktime((datetime(2009, 1, 1, 0, 0, 0) + timedelta(days=i)).timetuple())
            db.session.add(s)
        for i in range(404):
            s = Scrobble()
            s.user = mutantcornholio
            s.artist = "Burial"
            s.track = "Track #%d" % i
            s.uts = time.mktime((datetime(2012, 1, 1, 0, 0, 0) + timedelta(days=i)).timetuple())
            db.session.add(s)
        db.session.commit()

        tweet_milestones()
        post_tweet.assert_not_called()

        s = Scrobble()
        s.user = themylogin
        s.artist = "Burial"
        s.track = "Lambeth"
        s.uts = time.mktime((datetime(2015, 9, 25, 22, 00, 00)).timetuple())
        db.session.add(s)
        db.session.commit()

        tweet_milestones()
        post_tweet.assert_not_called()


class ChartChangeTweetTestCase(unittest.TestCase):
    def test_nothing_changed(self):
        self.assertEqual(chart_change_tweet(["God Is An Astronaut",
                                             "Mogwai",
                                             "Access to Arasaka",
                                             "65daysofstatic",
                                             "Crystal Castles"],
                                            ["God Is An Astronaut",
                                             "Mogwai",
                                             "Access to Arasaka",
                                             "65daysofstatic",
                                             "Crystal Castles"]),
                         None)

    def test_single_eviction(self):
        self.assertEqual(chart_change_tweet(["God Is An Astronaut",
                                             "Mogwai",
                                             "Access to Arasaka",
                                             "65daysofstatic",
                                             "Crystal Castles"],
                                            ["God Is An Astronaut",
                                             "Mogwai",
                                             "Access to Arasaka",
                                             "65daysofstatic",
                                             "Hadouken!"]),
                         "А у меня Hadouken! вытеснили Crystal Castles!")

    def test_multiple_eviction(self):
        self.assertEqual(chart_change_tweet(["God Is An Astronaut",
                                             "Mogwai",
                                             "Access to Arasaka",
                                             "65daysofstatic",
                                             "Crystal Castles"],
                                            ["God Is An Astronaut",
                                             "Mogwai",
                                             "Access to Arasaka",
                                             "Hadouken!",
                                             "Halou"]),
                         "А у меня Hadouken! и Halou вытеснили 65daysofstatic и Crystal Castles!")

    def test_single_overtake(self):
        self.assertEqual(chart_change_tweet(["God Is An Astronaut",
                                             "Mogwai",
                                             "Access to Arasaka",
                                             "65daysofstatic",
                                             "Crystal Castles"],
                                            ["Mogwai",
                                             "God Is An Astronaut",
                                             "Access to Arasaka",
                                             "65daysofstatic",
                                             "Crystal Castles"]),
                         "А у меня Mogwai обогнали God Is An Astronaut!")

    def test_double_overtake(self):
        self.assertEqual(chart_change_tweet(["God Is An Astronaut",
                                             "Mogwai",
                                             "Access to Arasaka",
                                             "65daysofstatic",
                                             "Crystal Castles"],
                                            ["Access to Arasaka",
                                             "God Is An Astronaut",
                                             "Mogwai",
                                             "65daysofstatic",
                                             "Crystal Castles"]),
                         "А у меня Access to Arasaka обогнали God Is An Astronaut и Mogwai!")

    def test_double_overtaken(self):
        self.assertEqual(chart_change_tweet(["Rammstein",
                                             "Maybeshewill",
                                             "Ария"],
                                            ["Maybeshewill",
                                             "Ария",
                                             "Rammstein"]),
                         "А у меня Maybeshewill и Ария обогнали Rammstein!")

    def test_double_double_overtaken(self):
        self.assertEqual(chart_change_tweet(["Rammstein",
                                             "Ministry",
                                             "Maybeshewill",
                                             "Ария"],
                                            ["Maybeshewill",
                                             "Ministry",
                                             "Ария",
                                             "Rammstein"]),
                         "У меня Maybeshewill обогнали Rammstein и Ministry, а Ministry и Ария обогнали Rammstein!")

    def test_pseudo_double_overtaken(self):
        self.assertEqual(chart_change_tweet(["Rammstein",
                                             "Ministry",
                                             "Maybeshewill",
                                             "Ария"],
                                            ["Maybeshewill",
                                             "Rammstein",
                                             "Ария",
                                             "Ministry"]),
                         "У меня Maybeshewill обогнали Rammstein и Ministry, а Ария обогнали Ministry!")

    def test_double_overtake_and_overtaken(self):
        self.assertEqual(chart_change_tweet(["Rammstein",
                                             "Ministry",
                                             "Maybeshewill",
                                             "Ария"],
                                            ["Maybeshewill",
                                             "Ария",
                                             "Rammstein",
                                             "Ministry"]),
                         "А у меня Maybeshewill и Ария обогнали Rammstein и Ministry!")

    def test_messed_overtake(self):
        self.assertEqual(chart_change_tweet(["God Is An Astronaut",
                                             "Mogwai",
                                             "Access to Arasaka",
                                             "65daysofstatic",
                                             "Crystal Castles"],
                                            ["Access to Arasaka",
                                             "Mogwai",
                                             "God Is An Astronaut",
                                             "65daysofstatic",
                                             "Crystal Castles"]),
                         "У меня Access to Arasaka обогнали God Is An Astronaut и Mogwai, а "
                         "Mogwai обогнали God Is An Astronaut!")

    def test_both_overtake_and_eviction(self):
        self.assertEqual(chart_change_tweet(['Access to Arasaka',
                                             'Sonic Youth',
                                             'Crystal Castles',
                                             'Skytree',
                                             'Gridlock'],
                                            ['Access to Arasaka',
                                             'Sonic Youth',
                                             'Crystal Castles',
                                             'Gridlock',
                                             'A Place to Bury Strangers']),
                         "У меня Gridlock обогнали Skytree, а A Place to Bury Strangers вытеснили Skytree!")

    def test_simultaneous_eviction_and_overtake(self):
        self.assertEqual(chart_change_tweet(['Access to Arasaka',
                                             'Sonic Youth',
                                             'Crystal Castles',
                                             'Gridlock',
                                             'A Place to Bury Strangers'],
                                            ['Access to Arasaka',
                                             'Sonic Youth',
                                             'Crystal Castles',
                                             'Skytree',
                                             'Gridlock']),
                         "А у меня Skytree вытеснили A Place to Bury Strangers, обогнав Gridlock!")

    def test_overtake_and_multiple_eviction(self):
        self.assertEqual(chart_change_tweet(['Access to Arasaka',
                                             'Sonic Youth',
                                             'Crystal Castles',
                                             'Skytree1',
                                             'Skytree2',
                                             'Gridlock'],
                                            ['Access to Arasaka',
                                             'Sonic Youth',
                                             'Crystal Castles',
                                             'Gridlock',
                                             'A Place to Bury Strangers1',
                                             'A Place to Bury Strangers2']),
                         "У меня Gridlock обогнали Skytree1 и Skytree2, а A Place to Bury Strangers1 и "
                         "A Place to Bury Strangers2 вытеснили Skytree1 и Skytree2!")

class SlowpokeTestCase(FlaskIntegrationTestCase(app, db)):
    @patch("last_fm.cron.milestones.post_tweet")
    @patch("last_fm.cron.milestones.update_scrobbles_for_user")
    @patch("last_fm.cron.milestones.get_api_for_user")
    @patch("last_fm.cron.milestones.time")
    def test_he_finally_starts_listening(self, TIME, get_api_for_user, update_scrobbles_for_user, post_tweet):
        get_api_for_user.return_value = Mock(GetFriendIDs=Mock(return_value=[1, 2]))

        themylogin = User()
        themylogin.download_scrobbles = True
        themylogin.twitter_username = "themylogin"
        themylogin.twitter_data = {"id": 1}
        themylogin.twitter_win_artist_races = True
        themylogin.twitter_lose_artist_races = True
        db.session.add(themylogin)

        mutantcornholio = User()
        mutantcornholio.download_scrobbles = True
        mutantcornholio.twitter_username = "mutantcornholio"
        mutantcornholio.twitter_data = {"id": 2}
        mutantcornholio.twitter_win_artist_races = True
        mutantcornholio.twitter_lose_artist_races = True
        db.session.add(mutantcornholio)

        for i in range(2000):
            s = Scrobble()
            s.user = themylogin
            s.artist = "Mogwai"
            s.track = "Track #%d" % i
            s.uts = time.mktime((datetime(2011, 1, 1, 0, 0, 0) + timedelta(hours=i * 20)).timetuple())
            krayuiniyui_scrobble_mogwai = s.uts
            db.session.add(s)
        for i in range(200):
            s = Scrobble()
            s.user = mutantcornholio
            s.artist = "Mogwai"
            s.track = "Track #%d" % i
            s.uts = time.mktime((datetime(2010, 1, 1, 0, 0, 0) + timedelta(hours=i)).timetuple())
            db.session.add(s)
        db.session.commit()

        TIME.time = Mock(return_value=krayuiniyui_scrobble_mogwai + 86400 * 100)

        tweet_milestones()
        post_tweet.assert_not_called()

        for i in range(200):
            s = Scrobble()
            s.user = mutantcornholio
            s.artist = "Mogwai"
            s.track = "RAVE TAPES"
            s.uts = krayuiniyui_scrobble_mogwai + 86400 * 100 + i * 3600
            db.session.add(s)
            db.session.commit()

        TIME.time = Mock(return_value=krayuiniyui_scrobble_mogwai + 86400 * 100 + 200 * 3600 + 86400)

        tweet_milestones()
        self.assertEqual(post_tweet.call_count, 1)
        self.assertEqual(post_tweet.call_args_list[0][0][1], "Вот @themylogin уже больше 4 лет слушает Mogwai, а до меня только сейчас дошло :(")

    @patch("last_fm.cron.milestones.post_tweet")
    @patch("last_fm.cron.milestones.update_scrobbles_for_user")
    @patch("last_fm.cron.milestones.get_api_for_user")
    @patch("last_fm.cron.milestones.time")
    def test_he_finally_starts_listening_but_i_am_not_alone(self, TIME, get_api_for_user, update_scrobbles_for_user, post_tweet):
        get_api_for_user.return_value = Mock(GetFriendIDs=Mock(return_value=[1, 2, 3]))

        themylogin = User()
        themylogin.download_scrobbles = True
        themylogin.twitter_username = "themylogin"
        themylogin.twitter_data = {"id": 1}
        themylogin.twitter_win_artist_races = True
        themylogin.twitter_lose_artist_races = True
        db.session.add(themylogin)

        mutantcornholio = User()
        mutantcornholio.download_scrobbles = True
        mutantcornholio.twitter_username = "mutantcornholio"
        mutantcornholio.twitter_data = {"id": 2}
        mutantcornholio.twitter_win_artist_races = True
        mutantcornholio.twitter_lose_artist_races = True
        db.session.add(mutantcornholio)

        kseniya = User()
        kseniya.download_scrobbles = True
        kseniya.twitter_username = "yaetomogu"
        kseniya.twitter_data = {"id": 3}
        kseniya.twitter_win_artist_races = True
        kseniya.twitter_lose_artist_races = True
        db.session.add(kseniya)

        for i in range(2000):
            s = Scrobble()
            s.user = themylogin
            s.artist = "Mogwai"
            s.track = "Track #%d" % i
            s.uts = time.mktime((datetime(2011, 1, 1, 0, 0, 0) + timedelta(hours=i * 20)).timetuple())
            krayuiniyui_scrobble_mogwai = s.uts
            db.session.add(s)
        for i in range(1000):
            s = Scrobble()
            s.user = kseniya
            s.artist = "Mogwai"
            s.track = "Track #%d" % i
            s.uts = time.mktime((datetime(2012, 1, 1, 0, 0, 0) + timedelta(hours=i * 10)).timetuple())
            db.session.add(s)
        for i in range(200):
            s = Scrobble()
            s.user = mutantcornholio
            s.artist = "Mogwai"
            s.track = "Track #%d" % i
            s.uts = time.mktime((datetime(2010, 1, 1, 0, 0, 0) + timedelta(hours=i)).timetuple())
            db.session.add(s)
        db.session.commit()

        TIME.time = Mock(return_value=krayuiniyui_scrobble_mogwai + 86400 * 100)

        tweet_milestones()
        post_tweet.assert_not_called()

        for i in range(200):
            s = Scrobble()
            s.user = mutantcornholio
            s.artist = "Mogwai"
            s.track = "RAVE TAPES"
            s.uts = krayuiniyui_scrobble_mogwai + 86400 * 100 + i * 3600
            db.session.add(s)
            db.session.commit()

        TIME.time = Mock(return_value=krayuiniyui_scrobble_mogwai + 86400 * 100 + 200 * 3600 + 86400)

        tweet_milestones()
        self.assertEqual(post_tweet.call_count, 1)
        self.assertEqual(post_tweet.call_args_list[0][0][1], "Вот @themylogin уже больше 4 лет слушает Mogwai, а до меня только сейчас дошло :(")
