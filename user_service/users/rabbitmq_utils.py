import json
import pika
from django.conf import settings

def publish_event(exchange_name, routing_key, message_body):
    connection = pika.BlockingConnection(
        pika.ConnectionParameters(
            host=settings.RABBITMQ_HOST,
            port=settings.RABBITMQ_PORT,
            credentials=pika.PlainCredentials(
                settings.RABBITMQ_USER, settings.RABBITMQ_PASSWORD
            ),
        )
    )
    channel = connection.channel()
    channel.exchange_declare(exchange=exchange_name, exchange_type='topic', durable=True)

    body_str = json.dumps(message_body)

    channel.basic_publish(
        exchange=exchange_name,
        routing_key=routing_key,
        body=body_str
    )
    connection.close()
