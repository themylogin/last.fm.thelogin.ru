# -*- coding=utf-8 -*-
from __future__ import absolute_import, division, unicode_literals

import logging
import twitter

from last_fm.celery import cron
from last_fm.db import db
from last_fm.models import *
from last_fm.utils.twitter import get_api_for_user

logger = logging.getLogger(__name__)


@cron.job(hour="*/1", minute=0)
def revoke_twitter_tokens():
    for user in db.session.query(User).\
                           filter(User.twitter_username != None):
        try:
            try:
                get_api_for_user(user).VerifyCredentials()
            except twitter.TwitterError as e:
                if e.args[0][0]["code"] == 89:
                    logger.warning("%s's twitter token was revoked", user.twitter_username)
                    user.twitter_username = None
                    user.twitter_data = None
                    user.twitter_data_updated = None
                    user.twitter_oauth_token = None
                    user.twitter_oauth_token_secret = None
                    user.use_twitter_data = False
                else:
                    raise
        except:
            logger.exception("Exception while verifying credentials")

    db.session.commit()
