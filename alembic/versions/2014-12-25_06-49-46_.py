# -*- coding: utf-8 -*-
from __future__ import absolute_import, division, unicode_literals

revision = '2688aee6c99'
down_revision = u'4ac3ec8c8fe3'

from alembic import op
import sqlalchemy as sa

from last_fm.db import db
from last_fm.models import *


def upgrade():
    ### commands auto generated by Alembic - please adjust! ###
    op.add_column('user', sa.Column('hates_me', sa.Boolean(), nullable=True))
    ### end Alembic commands ###


def downgrade():
    ### commands auto generated by Alembic - please adjust! ###
    op.drop_column('user', 'hates_me')
    ### end Alembic commands ###
