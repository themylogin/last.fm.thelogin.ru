# -*- coding: utf-8 -*-
from __future__ import absolute_import, division, unicode_literals

revision = '3e61f22249de'
down_revision = u'4b625e2ed760'

from alembic import op
import sqlalchemy as sa

from last_fm.db import db
from last_fm.models import *


def upgrade():
    ### commands auto generated by Alembic - please adjust! ###
    op.create_table('event',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('title', sa.String(length=255), nullable=True),
    sa.Column('datetime', sa.DateTime(), nullable=True),
    sa.Column('url', sa.String(length=255), nullable=True),
    sa.Column('city', sa.String(length=255), nullable=True),
    sa.Column('country', sa.String(length=255), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('event_artist',
    sa.Column('event_id', sa.Integer(), nullable=True),
    sa.Column('artist_id', sa.Integer(), nullable=True),
    sa.ForeignKeyConstraint(['artist_id'], [u'artist.id'], ),
    sa.ForeignKeyConstraint(['event_id'], [u'event.id'], )
    )
    ### end Alembic commands ###


def downgrade():
    ### commands auto generated by Alembic - please adjust! ###
    op.drop_table('event_artist')
    op.drop_table('event')
    ### end Alembic commands ###