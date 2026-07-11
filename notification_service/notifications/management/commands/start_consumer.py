from django.core.management.base import BaseCommand
from notifications.consumer import start_consumer

class Command(BaseCommand):
    help = 'Start the RabbitMQ consumer for the Notification Service.'

    def handle(self, *args, **options):
        start_consumer()
