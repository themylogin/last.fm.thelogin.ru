# -*- coding: utf-8 -*-
from __future__ import absolute_import, division, unicode_literals

import twitter

from themyutils.pprint import pprint
from twitter_overkill.client import TwitterOverkill

from last_fm.app import app

twitter_overkill = TwitterOverkill("http://twitter-overkill")


def get_api_for_user(user):
    return twitter.Api(consumer_key=app.config["TWITTER_CONSUMER_KEY"],
                       consumer_secret=app.config["TWITTER_CONSUMER_SECRET"],
                       access_token_key=user.twitter_oauth_token,
                       access_token_secret=user.twitter_oauth_token_secret)


def post_tweet(user, tweet_s, hashtag=True):
    if not isinstance(tweet_s, list):
        tweet_s = [tweet_s]

    if hashtag:
        tweet_s = ["%s #last_fm_666" % x for x in tweet_s] + tweet_s

    if app.debug:
        print " --- Tweet for %s (%s) ---" % (user.username, user.twitter_username)
        pprint(tweet_s)
    else:
        twitter_overkill.tweet(get_api_for_user(user), tweet_s)
