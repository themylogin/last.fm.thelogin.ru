# -*- coding: utf-8 -*-
from __future__ import absolute_import, division, unicode_literals

revision = '1b005b1bd8fd'
down_revision = u'3e61f22249de'

from alembic import op
import sqlalchemy as sa

from last_fm.db import db
from last_fm.models import *


def upgrade():
    ### commands auto generated by Alembic - please adjust! ###
    op.add_column('anniversary', sa.Column('positive', sa.Boolean(), nullable=True))
    op.execute("UPDATE anniversary SET positive = 1")
    ### end Alembic commands ###


def downgrade():
    ### commands auto generated by Alembic - please adjust! ###
    op.drop_column('anniversary', 'positive')
    ### end Alembic commands ###