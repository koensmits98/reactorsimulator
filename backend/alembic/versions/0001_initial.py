"""create presets and simulation_runs, seed the presets

Revision ID: 0001
Revises:
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0001"
down_revision = None

PRESETS = [
    {
        "name": "Rod withdrawal",
        "description": (
            "A control rod is withdrawn at t = 10 s, adding +100 pcm. The power first jumps "
            "slightly (prompt jump), then settles into a slow exponential rise with a period "
            "set by the delayed neutrons."
        ),
        "parameters": {
            "initial_power": 1.0,
            "reactivity": [
                {"time_s": 0, "value": 0, "unit": "pcm"},
                {"time_s": 10, "value": 100, "unit": "pcm"},
            ],
            "end_time": 120,
        },
    },
    {
        "name": "Prompt critical excursion",
        "description": (
            "Reactivity jumps to +1.1 dollars at t = 1 s, above prompt critical. The power "
            "now rises on the prompt neutron time scale, in milliseconds instead of minutes."
        ),
        "parameters": {
            "initial_power": 1.0,
            "reactivity": [
                {"time_s": 0, "value": 0, "unit": "dollars"},
                {"time_s": 1, "value": 1.1, "unit": "dollars"},
            ],
            "end_time": 3,
        },
    },
    {
        "name": "SCRAM from full power",
        "description": (
            "All rods drop at t = 10 s (-5000 pcm). The power falls to about 10 % within a "
            "second (prompt drop), then decays slowly as the delayed neutron precursors die "
            "out, finally with the 80 s period of the longest-lived group."
        ),
        "parameters": {
            "initial_power": 1.0,
            "reactivity": [
                {"time_s": 0, "value": 0, "unit": "pcm"},
                {"time_s": 10, "value": -5000, "unit": "pcm"},
            ],
            "end_time": 300,
        },
    },
]


def upgrade() -> None:
    presets = op.create_table(
        "presets",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(100), nullable=False, unique=True),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("parameters", postgresql.JSONB(), nullable=False),
    )
    op.create_table(
        "simulation_runs",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("parameters", postgresql.JSONB(), nullable=False),
        sa.Column("results", postgresql.JSONB(), nullable=False),
        sa.Column("peak_power", sa.Float(), nullable=False),
        sa.Column("final_power", sa.Float(), nullable=False),
    )
    op.bulk_insert(presets, PRESETS)


def downgrade() -> None:
    op.drop_table("simulation_runs")
    op.drop_table("presets")
