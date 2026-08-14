from sqlalchemy import (
    Column,
    DateTime,
    Index,
    String,
    Table,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.schema import ForeignKey

from utils.basemodel import metadata

email_confirmations = Table(
    "email_confirmations",
    metadata,
    Column("id", UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")),
    Column("user_email_id", UUID(as_uuid=True), ForeignKey("user_emails.id"), nullable=False),
    Column("code", String(64), nullable=False),
    Column("expires_at", DateTime(timezone=True), nullable=False),
    Column(
        "created_at",
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
    ),
    Column("used_at", DateTime(timezone=True), nullable=True),
    Index("ix_email_confirmations_code", "code", unique=True),
)
