import json
import logging
import time

import pika
from django.conf import settings

from .models import NotificationLog
from .tasks import send_notification_email

logger = logging.getLogger(__name__)

QUEUE_NAME = 'notifications.events'
DLX_NAME = 'notifications.dlx'
DLQ_NAME = 'notifications.events.dlq'

# exchange -> routing keys this service consumes
BINDINGS = {
    'user_events': ['user_registered'],
    'task_events': ['task_created', 'task_assigned'],
}

RECONNECT_DELAY_SECONDS = 5


def _connection_parameters():
    return pika.ConnectionParameters(
        host=settings.RABBITMQ_HOST,
        port=settings.RABBITMQ_PORT,
        credentials=pika.PlainCredentials(
            settings.RABBITMQ_USER, settings.RABBITMQ_PASSWORD
        ),
    )


def _declare_topology(channel):
    """Durable named queue with a dead-letter exchange: events survive
    consumer downtime, and poison messages land in the DLQ instead of
    being lost or requeued forever."""
    channel.exchange_declare(exchange=DLX_NAME, exchange_type='fanout', durable=True)
    channel.queue_declare(queue=DLQ_NAME, durable=True)
    channel.queue_bind(exchange=DLX_NAME, queue=DLQ_NAME)

    channel.queue_declare(
        queue=QUEUE_NAME,
        durable=True,
        arguments={'x-dead-letter-exchange': DLX_NAME},
    )
    for exchange, routing_keys in BINDINGS.items():
        channel.exchange_declare(exchange=exchange, exchange_type='topic', durable=True)
        for key in routing_keys:
            channel.queue_bind(exchange=exchange, queue=QUEUE_NAME, routing_key=key)


def _callback(channel, method, properties, body):
    event_type = method.routing_key
    try:
        payload_str = body.decode('utf-8')
        payload = json.loads(payload_str)
        NotificationLog.objects.create(event_type=event_type, payload=payload_str)
        send_notification_email.delay(event_type, payload)
    except Exception:
        logger.exception('Failed to process %s event; dead-lettering', event_type)
        channel.basic_nack(delivery_tag=method.delivery_tag, requeue=False)
    else:
        channel.basic_ack(delivery_tag=method.delivery_tag)
        logger.info('Processed %s event', event_type)


def start_consumer():
    """
    Consume events from user_events and task_events. Reconnects with a
    fixed delay when the broker is unavailable.
    """
    connection = None
    while True:
        try:
            connection = pika.BlockingConnection(_connection_parameters())
            channel = connection.channel()
            _declare_topology(channel)
            channel.basic_qos(prefetch_count=10)
            channel.basic_consume(queue=QUEUE_NAME, on_message_callback=_callback)
            logger.info('Waiting for messages on %s. To exit press CTRL+C', QUEUE_NAME)
            channel.start_consuming()
        except (pika.exceptions.AMQPError, OSError) as exc:
            # OSError covers DNS failures (socket.gaierror) pika does not
            # wrap in AMQPConnectionError.
            logger.warning(
                'RabbitMQ unavailable (%s); retrying in %ss',
                exc, RECONNECT_DELAY_SECONDS,
            )
            time.sleep(RECONNECT_DELAY_SECONDS)
        except KeyboardInterrupt:
            logger.info('Consumer stopped')
            if connection is not None and connection.is_open:
                connection.close()
            break
