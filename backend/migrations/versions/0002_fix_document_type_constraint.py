"""Add 'attendance_policy' to hr_policy_documents.document_type check
constraint — the frontend's upload form (ChatbotPage.jsx) has always
offered "attendance policy" as a selectable document type, but the
constraint from the original schema.sql only ever allowed
('company_policy','leave_policy','code_of_conduct','compensation_policy',
'legal_compliance','it_policy','other'), never 'attendance_policy'. This
went unnoticed until a real upload of an Attendance & Working Hours policy
document hit the constraint and failed with a raw 500 error (surfacing to
the user as a generic "Network Error", since the frontend's fetch() had no
specific handling for a database-level integrity error).

Revision ID: 0002
Revises: 0001
Create Date: 2026-07-13
"""
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None

OLD_CHECK = (
    "document_type IN ('company_policy','leave_policy','code_of_conduct',"
    "'compensation_policy','legal_compliance','it_policy','other')"
)
NEW_CHECK = (
    "document_type IN ('company_policy','leave_policy','code_of_conduct',"
    "'compensation_policy','legal_compliance','it_policy','attendance_policy','other')"
)


def upgrade() -> None:
    op.execute(
        "ALTER TABLE hr_policy_documents "
        "DROP CONSTRAINT hr_policy_documents_document_type_check"
    )
    op.execute(
        f"ALTER TABLE hr_policy_documents "
        f"ADD CONSTRAINT hr_policy_documents_document_type_check CHECK ({NEW_CHECK})"
    )


def downgrade() -> None:
    op.execute(
        "ALTER TABLE hr_policy_documents "
        "DROP CONSTRAINT hr_policy_documents_document_type_check"
    )
    op.execute(
        f"ALTER TABLE hr_policy_documents "
        f"ADD CONSTRAINT hr_policy_documents_document_type_check CHECK ({OLD_CHECK})"
    )
