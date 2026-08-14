from celery import Celery
from settings import celery_app_settings
from kombu import Queue

celery_app = Celery(
    celery_app_settings.celery_app_main,
    broker=celery_app_settings.celery_app_broker,
    backend=celery_app_settings.celery_app_backend
)

celery_app.conf.task_queues = (
    Queue("email"),
)

celery_app.conf.task_default_queue = "email"