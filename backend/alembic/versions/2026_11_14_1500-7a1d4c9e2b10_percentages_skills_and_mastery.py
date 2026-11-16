"""percentages becomes a topic area with four skills; bigger question bank

Revision ID: 7a1d4c9e2b10
Revises: 3e9eb820d3e7
Create Date: 2026-11-14 15:00:00

No table changes: mastery tables exist since the first migration. This migration ends
lessons still open on the "Percentages" area, which has no questions of its own now.
The new skills and the move of the first 15 questions come from the seed command
(`python -m app.modules.curriculum.seed`), run after migrations.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '7a1d4c9e2b10'
down_revision: Union[str, Sequence[str], None] = '3e9eb820d3e7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    from app.modules.curriculum import seed_data as d

    op.execute(
        sa.text(
            "UPDATE learning_sessions SET status = 'ended', ended_at = now() "
            "WHERE topic_id = :area AND status = 'active'"
        ).bindparams(area=d.PERCENTAGES_ID)
    )


def downgrade() -> None:
    from app.modules.curriculum import seed_data as d

    skills = [d.CONVERT_ID, d.CHANGE_ID, d.EXPRESS_ID]
    params = {"area": d.PERCENTAGES_ID, "of": d.PERCENT_OF_ID}
    # The first 15 questions and their misconceptions go back to the area topic.
    op.execute(sa.text("UPDATE questions SET topic_id = :area WHERE topic_id = :of").bindparams(**params))
    op.execute(sa.text("UPDATE misconceptions SET topic_id = :area WHERE topic_id = :of").bindparams(**params))
    op.execute(sa.text("UPDATE learning_sessions SET topic_id = :area WHERE topic_id = :of").bindparams(**params))
    op.execute(sa.text("DELETE FROM topic_mastery WHERE topic_id = :of").bindparams(of=d.PERCENT_OF_ID))
    op.execute(sa.text("DELETE FROM mastery_events WHERE topic_id = :of").bindparams(of=d.PERCENT_OF_ID))
    op.execute(sa.text("DELETE FROM topic_prerequisites"))
    for topic in skills:
        # Attempts on the new skills' questions block deleting them (RESTRICT): remove the
        # lessons first; their attempts and messages go with them (CASCADE).
        op.execute(sa.text("DELETE FROM learning_sessions WHERE topic_id = :t").bindparams(t=topic))
        op.execute(sa.text("DELETE FROM topics WHERE id = :t").bindparams(t=topic))
    op.execute(sa.text("DELETE FROM topics WHERE id = :of").bindparams(of=d.PERCENT_OF_ID))
