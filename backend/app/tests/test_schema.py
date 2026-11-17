"""Checks the migrated database matches the blueprint and our design rules."""

from app.db_models import Base
from app.tests.helpers import query

BLUEPRINT_TABLES = {
    "users",
    "student_profiles",
    "guardian_links",
    "subjects",
    "topics",
    "topic_prerequisites",
    "misconceptions",
    "questions",
    "learning_sessions",
    "messages",
    "question_attempts",
    "topic_mastery",
    "mastery_events",
    "ai_requests",
    "audit_log",
}
# Added in Phase 3 for login tokens, guardian invitations (see README).
PHASE_3_TABLES = {"refresh_tokens", "guardian_invites"}
# Multi-subject plan, phase 1: the catalogue above subjects and below topics.
CATALOGUE_TABLES = {"disciplines", "courses", "learning_objectives"}
DOCUMENT_TABLES = {"documents"}  # phase 2: uploads
PROCESSING_TABLES = {"document_pages", "document_chunks", "jobs"}  # phase 3
ALL_TABLES = (
    BLUEPRINT_TABLES | PHASE_3_TABLES | CATALOGUE_TABLES | DOCUMENT_TABLES | PROCESSING_TABLES
)


def test_models_define_all_tables() -> None:
    assert set(Base.metadata.tables) == ALL_TABLES


def test_migrated_database_has_all_tables() -> None:
    rows = query("SELECT table_name FROM information_schema.tables WHERE table_schema = 'public'")
    assert ALL_TABLES <= {r[0] for r in rows}


def test_every_table_has_created_at() -> None:
    rows = query(
        "SELECT table_name FROM information_schema.columns "
        "WHERE table_schema = 'public' AND column_name = 'created_at'"
    )
    assert ALL_TABLES <= {r[0] for r in rows}


def test_student_data_is_deleted_with_the_user() -> None:
    """Deletion really deletes: every FK from student data to users cascades."""
    rows = query(
        """
        SELECT tc.table_name, kcu.column_name, rc.delete_rule
        FROM information_schema.referential_constraints rc
        JOIN information_schema.table_constraints tc ON tc.constraint_name = rc.constraint_name
        JOIN information_schema.key_column_usage kcu ON kcu.constraint_name = rc.constraint_name
        JOIN information_schema.constraint_column_usage ccu
             ON ccu.constraint_name = rc.constraint_name
        WHERE ccu.table_name = 'users'
        """
    )
    rules = {(t, c): rule for t, c, rule in rows}
    assert rules.pop(("audit_log", "actor_id")) == "SET NULL"
    # Who uploaded a document (later: a guardian for a child). The document belongs to its
    # owner, and documents.owner_id does cascade, so deleting the uploader keeps it.
    assert rules.pop(("documents", "uploaded_by_id")) == "SET NULL"
    assert rules, "expected foreign keys to users"
    assert all(rule == "CASCADE" for rule in rules.values()), rules
