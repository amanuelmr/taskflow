import json
from unittest.mock import MagicMock, patch

import pytest
from django.core import mail

from notifications.consumer import _callback
from notifications.models import NotificationLog
from notifications.tasks import send_notification_email

pytestmark = pytest.mark.django_db


class TestLogsEndpoint:
    def test_unauthenticated_rejected(self, api_client):
        assert api_client.get('/api/logs/').status_code == 401

    def test_authenticated_can_read(self, auth_client):
        NotificationLog.objects.create(event_type='task_created', payload='{}')
        response = auth_client.get('/api/logs/')
        assert response.status_code == 200
        assert response.data['count'] == 1


class TestConsumerCallback:
    def _method(self, routing_key='task_created'):
        method = MagicMock()
        method.routing_key = routing_key
        method.delivery_tag = 42
        return method

    def test_valid_message_logged_and_acked(self):
        channel = MagicMock()
        body = json.dumps({'task_id': 1, 'owner_id': 2}).encode()
        with patch('notifications.consumer.send_notification_email') as task:
            _callback(channel, self._method(), None, body)
        assert NotificationLog.objects.filter(event_type='task_created').exists()
        task.delay.assert_called_once_with('task_created', {'task_id': 1, 'owner_id': 2})
        channel.basic_ack.assert_called_once_with(delivery_tag=42)
        channel.basic_nack.assert_not_called()

    def test_malformed_message_dead_lettered(self):
        channel = MagicMock()
        _callback(channel, self._method(), None, b'not json')
        channel.basic_nack.assert_called_once_with(delivery_tag=42, requeue=False)
        channel.basic_ack.assert_not_called()


class TestNotificationEmails:
    def test_user_registered_sends_welcome_email(self):
        send_notification_email('user_registered',
                                {'email': 'new@example.com', 'username': 'new'})
        assert len(mail.outbox) == 1
        assert mail.outbox[0].to == ['new@example.com']

    def test_task_events_do_not_email(self):
        send_notification_email('task_created', {'task_id': 1})
        send_notification_email('task_assigned', {'task_id': 1, 'assigned_user_id': 2})
        assert mail.outbox == []
