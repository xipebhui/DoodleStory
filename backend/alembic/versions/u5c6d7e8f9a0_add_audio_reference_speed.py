"""add audio reference speech speed

Revision ID: u5c6d7e8f9a0
Revises: t4b5c6d7e8f9
Create Date: 2026-06-26 00:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "u5c6d7e8f9a0"
down_revision: Union[str, None] = "t4b5c6d7e8f9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("audio_references", sa.Column("speech_speed", sa.Float(), nullable=False, server_default="1.0"))
    op.add_column("video_tasks", sa.Column("voice_speed_snapshot", sa.Float(), nullable=False, server_default="1.0"))


def downgrade() -> None:
    op.drop_column("video_tasks", "voice_speed_snapshot")
    op.drop_column("audio_references", "speech_speed")
