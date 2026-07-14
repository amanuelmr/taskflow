"""RabbitMQ event publishing, offloaded to Celery so the HTTP request path
never blocks on (or fails because of) the broker.

NOTE: this module is intentionally byte-identical in user_service and
task_service — the services share no code at runtime, so keep edits in sync.
"""
import json
import logging

import pika
from celery import shared_task
from django.conf import settings

logger = logging.getLogger(__name__)


def _connection_parameters():
    return pika.ConnectionParameters(
        host=settings.RABBITMQ_HOST,
        port=settings.RABBITMQ_PORT,
        credentials=pika.PlainCredentials(
            settings.RABBITMQ_USER, settings.RABBITMQ_PASSWORD
        ),
    )


@shared_task(
    autoretry_for=(pika.exceptions.AMQPError, OSError),
    retry_backoff=True,
    retry_backoff_max=300,
    max_retries=5,
)
def publish_event_task(exchange_name, routing_key, message_body):
    connection = pika.BlockingConnection(_connection_parameters())
    try:
        channel = connection.channel()
        channel.exchange_declare(
            exchange=exchange_name, exchange_type='topic', durable=True
        )
        channel.basic_publish(
            exchange=exchange_name,
            routing_key=routing_key,
            body=json.dumps(message_body),
            properties=pika.BasicProperties(delivery_mode=2),  # persistent
        )
    finally:
        connection.close()


def publish_event(exchange_name, routing_key, message_body):
    """Enqueue the publish on Celery. Never raises into the caller: if the
    broker is unreachable the failure is logged and the API request still
    succeeds."""
    try:
        publish_event_task.delay(exchange_name, routing_key, message_body)
    except Exception:
        logger.exception('Failed to enqueue %s event for %s', routing_key, exchange_name)
