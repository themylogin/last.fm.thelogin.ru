# -*- coding=utf-8 -*-
from __future__ import absolute_import, division, unicode_literals

import unittest

from last_fm.cron.milestones import chart_change_tweet


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
                         "У меня Access to Arasaka обогнали God Is An Astronaut и Mogwai, а Mogwai обогнали God Is An Astronaut!")
