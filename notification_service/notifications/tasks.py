import logging

from celery import shared_task
from django.conf import settings
from django.core.mail import send_mail

logger = logging.getLogger(__name__)


@shared_task(retry_backoff=True, max_retries=3)
def send_notification_email(event_type, payload):
    """
    Send a notification email for an event. Task/assignment events carry
    only user ids (emails live in the user service), so they are logged;
    an email is sent only when the payload includes an address.
    """
    if event_type == 'user_registered':
        email = payload.get('email')
        username = payload.get('username', 'there')
        if email:
            send_mail(
                'Welcome to Task Manager',
                f'Hi {username}, your account has been created.',
                settings.DEFAULT_FROM_EMAIL,
                [email],
            )
    elif event_type == 'task_created':
        logger.info(
            'Task %s created by user %s',
            payload.get('task_id'), payload.get('owner_id'),
        )
    elif event_type == 'task_assigned':
        logger.info(
            'Task %s assigned to user %s',
            payload.get('task_id'), payload.get('assigned_user_id'),
        )
    else:
        logger.warning('Unhandled event type: %s', event_type)
    return True
