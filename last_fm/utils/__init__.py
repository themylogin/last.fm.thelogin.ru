# -*- coding: utf-8 -*-
from __future__ import absolute_import, unicode_literals

import urllib


def normalize_mac_address(address):
    return address.lower().replace("-", ":")


def urlencode(s):
    return urllib.quote(s.encode("utf-8"), "")


def urlencode_plus(s):
    return urllib.quote_plus(s.encode("utf-8"), "")
