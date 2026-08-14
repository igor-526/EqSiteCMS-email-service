from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Index,
    String,
    Table,
    text,
)
from sqlalchemy.dialects.postgresql import UUID

from utils.basemodel import metadata

user_emails = Table(
    "user_emails",
    metadata,
    Column("id", UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")),
    Column("user_id", UUID(as_uuid=True), nullable=False),
    Column("email", String(255), nullable=False),
    Column("approved", Boolean, nullable=False, server_default=text("false")),
    Column("deleted_at", DateTime(timezone=True), nullable=True),
    Column(
        "created_at",
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
    ),
    Column(
        "updated_at",
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
    ),
    Index(
        "uq_user_emails_user_id_active",
        "user_id",
        unique=True,
        postgresql_where=text("deleted_at IS NULL"),
    ),
    Index(
        "uq_user_emails_email_active",
        "email",
        unique=True,
        postgresql_where=text("deleted_at IS NULL"),
    ),
)
