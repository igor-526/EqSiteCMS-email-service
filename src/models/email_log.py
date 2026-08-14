from sqlalchemy import (
    Column,
    DateTime,
    Index,
    Integer,
    String,
    Table,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import JSON, UUID

from utils.basemodel import metadata

email_logs = Table(
    "email_logs",
    metadata,
    Column("id", UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")),
    Column("event_uuid", UUID(as_uuid=True), unique=True, nullable=False),
    Column("to", JSON, nullable=False),
    Column("subject", String(500), nullable=False),
    Column("body", Text, nullable=False),
    Column("cc", JSON, nullable=True),
    Column("bcc", JSON, nullable=True),
    Column("reply_to", String(255), nullable=True),
    Column("from_name", String(255), nullable=True),
    Column("from_email", String(255), nullable=True),
    Column("status", String(50), nullable=False, server_default=text("'pending'")),
    Column("error_message", Text, nullable=True),
    Column("attempts", Integer, nullable=False, server_default=text("0")),
    Column("created_at", DateTime(timezone=True), nullable=False, server_default=text("now()")),
    Column("sent_at", DateTime(timezone=True), nullable=True),
    Column("updated_at", DateTime(timezone=True), nullable=False, server_default=text("now()")),
    Index("ix_email_logs_event_uuid", "event_uuid", unique=True),
    Index("ix_email_logs_status", "status"),
    Index("ix_email_logs_created_at", "created_at"),
)
