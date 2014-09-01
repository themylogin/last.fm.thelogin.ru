<%text># -*- coding: utf-8 -*-</%text>
from __future__ import absolute_import, division, unicode_literals

revision = ${repr(up_revision)}
down_revision = ${repr(down_revision)}

from alembic import op
import sqlalchemy as sa

from last_fm.db import db
from last_fm.models import *
${imports if imports else ""}

def upgrade():
    ${upgrades if upgrades else "pass"}


def downgrade():
    ${downgrades if downgrades else "pass"}
