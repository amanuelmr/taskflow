import json
import pika
from django.conf import settings
from .models import NotificationLog
from .tasks import send_notification_email

def start_consumer():
    """
    Consumes events from user_events and task_events.
    """
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

    # Declare the exchanges
    channel.exchange_declare(exchange='user_events', exchange_type='topic', durable=True)
    channel.exchange_declare(exchange='task_events', exchange_type='topic', durable=True)

    # Create random queues for user_events
    user_result = channel.queue_declare(queue='', exclusive=True)
    user_queue_name = user_result.method.queue
    channel.queue_bind(exchange='user_events', queue=user_queue_name, routing_key='user_registered')

    # For task_events
    task_result = channel.queue_declare(queue='', exclusive=True)
    task_queue_name = task_result.method.queue
    channel.queue_bind(exchange='task_events', queue=task_queue_name, routing_key='task_created')
    channel.queue_bind(exchange='task_events', queue=task_queue_name, routing_key='task_assigned')

    def callback(ch, method, properties, body):
        event_type = method.routing_key
        payload_str = body.decode('utf-8')
        NotificationLog.objects.create(event_type=event_type, payload=payload_str)

        payload = json.loads(payload_str)
        # Offload email sending to Celery
        send_notification_email.delay(event_type, payload)

    channel.basic_consume(queue=user_queue_name, on_message_callback=callback, auto_ack=True)
    channel.basic_consume(queue=task_queue_name, on_message_callback=callback, auto_ack=True)

    print(" [*] Waiting for messages in Notification Service. To exit press CTRL+C")
    channel.start_consuming()