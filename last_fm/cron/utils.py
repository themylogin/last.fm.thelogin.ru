# -*- coding: utf-8 -*-
from __future__ import absolute_import, unicode_literals

from celery.schedules import crontab

from last_fm.celery_ import celery

jobs = {}


def job(*crontab_args, **crontab_kwargs):
    def decorator(func):
        celery_task = celery.task(func)

        celery.conf.CELERYBEAT_SCHEDULE[celery_task.name] = {
            "task":     celery_task.name,
            "schedule": crontab(*crontab_args, **crontab_kwargs),
        }

        jobs[celery_task.name] = func

    return decorator
