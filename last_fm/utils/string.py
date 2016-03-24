# -*- coding=utf-8 -*-
from __future__ import absolute_import, division, unicode_literals

import logging

logger = logging.getLogger(__name__)

__all__ = [b"streq"]


def streq(s1, s2):
    s1l = s1.lower()
    s2l = s2.lower()
    return s1l.startswith(s2l) or s2l.startswith(s1l)
