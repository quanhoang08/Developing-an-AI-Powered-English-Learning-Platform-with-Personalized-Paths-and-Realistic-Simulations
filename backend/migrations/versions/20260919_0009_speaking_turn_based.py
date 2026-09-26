"""Speaking turn-based (feature-speaking.md mục 1): bổ sung cột còn thiếu cho scenarios /
conversation_turns và seed vài kịch bản mẫu.

Bảng scenarios/conversation_sessions/conversation_turns đã có sẵn trong DB thật (schema.sql
gốc); chỉ ALTER thêm cột theo mục 1.4 và 3.3 (goal, formality_level, stt_provider_used,
pronunciation_assessment_failed, feedback + suggested_phrases) — bảo thủ, không tạo bảng mới.
"""

from alembic import op
from sqlalchemy import Boolean, Column, String, Text, inspect, text
from sqlalchemy.dialects.postgresql import JSONB


revision = "20260919_0009"
down_revision = "20260917_0008"
branch_labels = None
depends_on = None

_SEED_SCENARIOS = [
    ("Ordering at a restaurant", "You are a waiter at a busy restaurant taking a customer's order.",
     "a1", "Order a meal and a drink politely and ask about one menu item", "neutral"),
    ("Job interview greeting", "You are an interviewer opening a job interview for a junior marketing role.",
     "b1", "Introduce yourself and explain why you want the job", "formal"),
    ("Chatting with a new classmate", "You are a friendly classmate meeting the learner for the first time.",
     "a2", "Introduce yourself and find one thing you have in common", "casual"),
    ("Returning a faulty product", "You are a shop assistant. The customer wants to return a broken headset.",
     "b1", "Explain the problem and politely ask for a refund or replacement", "neutral"),
]


def upgrade() -> None:
    inspector = inspect(op.get_bind())

    scenario_columns = {c["name"] for c in inspector.get_columns("scenarios")}
    if "goal" not in scenario_columns:
        op.add_column("scenarios", Column("goal", Text(), nullable=True))
    if "formality_level" not in scenario_columns:
        op.add_column(
            "scenarios",
            Column("formality_level", String(20), nullable=False, server_default=text("'neutral'")),
        )

    turn_columns = {c["name"] for c in inspector.get_columns("conversation_turns")}
    additions = [
        Column("stt_provider_used", String(20), nullable=True),
        Column("pronunciation_assessment_failed", Boolean(), nullable=False, server_default=text("false")),
        Column("intent_feedback", Text(), nullable=True),
        Column("politeness_feedback", Text(), nullable=True),
        Column("suggested_phrases", JSONB(), nullable=True),
    ]
    for column in additions:
        if column.name not in turn_columns:
            op.add_column("conversation_turns", column)

    existing = op.get_bind().execute(text("SELECT count(*) FROM scenarios")).scalar()
    if not existing:
        for title, description, level, goal, formality in _SEED_SCENARIOS:
            op.get_bind().execute(
                text(
                    "INSERT INTO scenarios (title, description, difficulty_level, goal, formality_level)"
                    " VALUES (:t, :d, :l, :g, :f)"
                ),
                {"t": title, "d": description, "l": level, "g": goal, "f": formality},
            )


def downgrade() -> None:
    for name in ("suggested_phrases", "politeness_feedback", "intent_feedback",
                 "pronunciation_assessment_failed", "stt_provider_used"):
        op.drop_column("conversation_turns", name)
    op.drop_column("scenarios", "formality_level")
    op.drop_column("scenarios", "goal")
