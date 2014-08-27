# -*- coding: utf-8 -*-
from __future__ import absolute_import, division, unicode_literals


def get_user_data(authenticated_user):
    data = {}
    for k in authenticated_user._request("user.getInfo", True).getElementsByTagName('*'):
        if k.firstChild and k.firstChild.nodeValue.strip() != "":
            data[k.tagName] = k.firstChild.nodeValue 
    return data
