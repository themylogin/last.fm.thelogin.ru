# -*- coding: utf-8 -*-
from __future__ import absolute_import, division, unicode_literals

revision = '3eb79129ab72'
down_revision = u'4672e36fa037'

from alembic import op
import sqlalchemy as sa

from last_fm.db import db
from last_fm.models import *


def upgrade():
    ### commands auto generated by Alembic - please adjust! ###
    op.add_column('user_artist', sa.Column('first_real_scrobble_corrected', sa.Integer(), nullable=True))
    ### end Alembic commands ###


def downgrade():
    ### commands auto generated by Alembic - please adjust! ###
    op.drop_column('user_artist', 'first_real_scrobble_corrected')
    ### end Alembic commands ###