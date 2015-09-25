# -*- coding=utf-8 -*-
from __future__ import absolute_import, division, unicode_literals

from datetime import datetime, timedelta
from mock import Mock, patch
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
        themylogin.twitter_artist_races_min_count = 250
        themylogin.twitter_win_artist_races = True
        themylogin.twitter_lose_artist_races = True
        db.session.add(themylogin)

        mutantcornholio = User()
        mutantcornholio.download_scrobbles = True
        mutantcornholio.twitter_username = "mutantcornholio"
        mutantcornholio.twitter_data = {"id": 2}
        mutantcornholio.twitter_artist_races_min_count = 250
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
        self.assertFalse(post_tweet.called)

        s = Scrobble()
        s.user = themylogin
        s.artist = "Burial"
        s.track = "Lambeth"
        s.uts = time.mktime((datetime(2015, 9, 25, 22, 00, 00)).timetuple())
        db.session.add(s)
        db.session.commit()

        tweet_milestones()
        self.assertFalse(post_tweet.called)


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
