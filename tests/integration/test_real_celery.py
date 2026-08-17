import asyncio
import os
import subprocess
import time
import uuid
from collections.abc import Generator
from datetime import UTC, datetime
from typing import cast

import pytest
from celery import Celery
from redis import Redis
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from models.email_log import email_logs


def _wait_until(predicate: object, timeout: float = 15) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if callable(predicate) and predicate():
            return
        time.sleep(0.1)
    raise AssertionError("condition was not met before the bounded timeout")


@pytest.fixture
def real_celery() -> Generator[tuple[Celery, Redis, str]]:
    broker = os.environ["EMAIL_TEST_CELERY_BROKER"]
    backend = os.environ["EMAIL_TEST_CELERY_BACKEND"]
    app = Celery("email-integration-test", broker=broker, backend=backend)
    app.conf.broker_transport_options = {"visibility_timeout": 5}
    redis = Redis.from_url(broker, decode_responses=True)
    probe_id = uuid.uuid4().hex
    try:
        assert redis.ping()
        yield app, redis, probe_id
    finally:
        for key in redis.scan_iter(f"eqsitecms:integration:{probe_id}:*"):
            redis.delete(key)


@pytest.mark.infrastructure
def test_real_delivery_retry_acks_late_and_idempotency(real_celery: tuple[Celery, Redis, str]) -> None:
    app, redis, probe_id = real_celery
    first = app.send_task(
        "email.integration_probe",
        args=[probe_id],
        kwargs={"fail_until": 1},
        queue="email",
    ).get(timeout=15)
    second = app.send_task("email.integration_probe", args=[probe_id], queue="email").get(timeout=15)

    assert first == {"acks_late": True, "attempts": 2, "effect": "created"}
    assert second == {"acks_late": True, "attempts": 3, "effect": "duplicate"}
    assert redis.get(f"eqsitecms:integration:{probe_id}:effect") == "1"


@pytest.mark.infrastructure
def test_unacked_task_is_redelivered_after_worker_restart(real_celery: tuple[Celery, Redis, str]) -> None:
    app, redis, probe_id = real_celery
    result = app.send_task(
        "email.integration_probe",
        args=[probe_id],
        kwargs={"delay_seconds": 8},
        queue="email",
    )
    _wait_until(lambda: redis.exists(f"eqsitecms:integration:{probe_id}:started") == 1)

    subprocess.run(["docker", "kill", "eqsitecms-email-celery-worker"], check=True, timeout=10)
    subprocess.run(["docker", "start", "eqsitecms-email-celery-worker"], check=True, timeout=10)

    def worker_is_ready() -> bool:
        result = subprocess.run(
            [
                "docker",
                "exec",
                "eqsitecms-email-celery-worker",
                "uv",
                "run",
                "--no-sync",
                "celery",
                "-A",
                "workers.celery_app",
                "inspect",
                "ping",
                "--destination",
                "email-worker@email-worker",
                "--timeout",
                "2",
            ],
            capture_output=True,
            timeout=5,
        )
        return result.returncode == 0

    _wait_until(worker_is_ready, timeout=20)
    # Deterministically trigger the Redis transport's expired-unacked sweep.
    time.sleep(6)
    with app.connection_for_read() as connection:
        channel = connection.channel()
        channel.qos.restore_visible(start=0, num=100, interval=1)

    assert result.get(timeout=15)["effect"] == "created"
    attempts = cast(str | None, redis.get(f"eqsitecms:integration:{probe_id}:attempts"))
    assert int(attempts or 0) >= 2


@pytest.mark.infrastructure
@pytest.mark.asyncio
async def test_sequential_confirmation_tasks_use_event_loop_local_database_resources(
    real_celery: tuple[Celery, Redis, str],
) -> None:
    app, _, _ = real_celery
    database_url = os.environ["EMAIL_TEST_DATABASE_URL"]
    engine = create_async_engine(database_url)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    user_ids = [uuid.uuid4(), uuid.uuid4()]
    started_at = datetime.now(UTC)

    try:
        results = [
            app.send_task("email.send_confirmation", args=[str(user_id)], queue="email").get(timeout=15)
            for user_id in user_ids
        ]

        assert results == [
            {"status": "error", "message": "email not found"},
            {"status": "error", "message": "email not found"},
        ]

        async with session_factory() as session:
            statement = (
                select(func.count())
                .select_from(email_logs)
                .where(
                    email_logs.c.subject == "send_confirmation",
                    email_logs.c.body.in_(
                        [f'{{"user_id": "{user_id}", "reason": "email_not_found"}}' for user_id in user_ids]
                    ),
                )
            )
            assert await session.scalar(statement) == 2

        worker_logs = await asyncio.to_thread(
            subprocess.run,
            ["docker", "logs", "--since", started_at.isoformat(), "eqsitecms-email-celery-worker"],
            check=True,
            capture_output=True,
            text=True,
            timeout=10,
        )
        combined_logs = worker_logs.stdout + worker_logs.stderr
        assert all(str(user_id) in combined_logs for user_id in user_ids)
        assert "attached to a different loop" not in combined_logs
        assert "Event loop is closed" not in combined_logs
        assert "Retry in" not in combined_logs
        assert "Traceback (most recent call last)" not in combined_logs
    finally:
        async with session_factory() as session, session.begin():
            await session.execute(
                delete(email_logs).where(
                    email_logs.c.subject == "send_confirmation",
                    email_logs.c.body.in_(
                        [f'{{"user_id": "{user_id}", "reason": "email_not_found"}}' for user_id in user_ids]
                    ),
                )
            )
        await engine.dispose()
