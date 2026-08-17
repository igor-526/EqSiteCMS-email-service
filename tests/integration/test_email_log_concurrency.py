import asyncio
import os
import uuid

import pytest
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from core.schemas.messaging import NotificationCommandSendEmailData
from core.services.email_processing import EmailProcessingService
from models.email_log import email_logs
from repositories.email_log import SQLAlchemyEmailLogRepository


class _UnusedSender:
    async def send(self, **_: object) -> None:
        raise AssertionError("SMTP must not run while accepting a NATS command")


@pytest.mark.infrastructure
async def test_concurrent_duplicate_event_creates_and_dispatches_once() -> None:
    database_url = os.environ["EMAIL_TEST_DATABASE_URL"]
    engine = create_async_engine(database_url, pool_size=5)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    event_uuid = uuid.uuid4()
    payload = NotificationCommandSendEmailData(
        event_uuid=event_uuid,
        to=["integration@example.test"],
        subject="concurrency",
        body="test",
    )

    async def process() -> uuid.UUID | None:
        async with session_factory() as session, session.begin():
            service = EmailProcessingService(
                repository=SQLAlchemyEmailLogRepository(session),
                email_sender=_UnusedSender(),
            )
            return await service.process_incoming_event(payload=payload)

    try:
        results = await asyncio.wait_for(asyncio.gather(*(process() for _ in range(8))), timeout=10)
        created = [result for result in results if result is not None]
        assert len(created) == 1

        async with session_factory() as session:
            stored = await SQLAlchemyEmailLogRepository(session).find_by_event_uuid(event_uuid=event_uuid)
            assert stored is not None
            assert stored["id"] == created[0]
    finally:
        async with session_factory() as session, session.begin():
            await session.execute(delete(email_logs).where(email_logs.c.event_uuid == event_uuid))
        await engine.dispose()
