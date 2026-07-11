import jwt as pyjwt
import pytest

from tasks.models import Task

pytestmark = pytest.mark.django_db


def create_task(client, **overrides):
    return client.post('/api/tasks/', {'title': 'Write report', **overrides})


class TestAuthentication:
    def test_unauthenticated_rejected(self, api_client):
        assert api_client.get('/api/tasks/').status_code == 401

    def test_valid_token_accepted(self, alice):
        # Regression: SimpleUser lacked is_authenticated and every request 500'd
        assert alice.get('/api/tasks/').status_code == 200

    def test_hs256_token_with_old_shared_secret_rejected(self, api_client):
        token = pyjwt.encode(
            {'token_type': 'access', 'user_id': 1, 'jti': 'x'},
            'mysharedsecretkey123',
            algorithm='HS256',
        )
        api_client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
        assert api_client.get('/api/tasks/').status_code == 401


class TestOwnership:
    def test_create_sets_owner_from_token(self, alice, published):
        response = create_task(alice)
        assert response.status_code == 201
        assert response.data['owner_id'] == 1
        assert published[-1]['routing_key'] == 'task_created'

    def test_client_cannot_spoof_owner(self, alice):
        response = create_task(alice, owner_id=999)
        assert response.status_code == 201
        assert response.data['owner_id'] == 1  # read-only field ignored

    def test_cross_user_isolation(self, alice, bob):
        task_id = create_task(alice).data['id']

        assert bob.get('/api/tasks/').data['results'] == []
        assert bob.get(f'/api/tasks/{task_id}/').status_code == 404
        assert bob.patch(f'/api/tasks/{task_id}/', {'title': 'hacked'}).status_code == 404
        assert bob.delete(f'/api/tasks/{task_id}/').status_code == 404
        assert bob.post(f'/api/tasks/{task_id}/assign/', {'user_id': 2}).status_code == 404

    def test_assignee_can_read_but_not_write(self, alice, bob):
        task_id = create_task(alice).data['id']
        alice.post(f'/api/tasks/{task_id}/assign/', {'user_id': 2})

        assert bob.get(f'/api/tasks/{task_id}/').status_code == 200
        assert bob.patch(f'/api/tasks/{task_id}/', {'title': 'hacked'}).status_code == 403


class TestValidation:
    def test_invalid_status_rejected(self, alice):
        assert create_task(alice, status='Bogus').status_code == 400

    def test_valid_status_choices(self, alice):
        assert create_task(alice, status='In Progress').status_code == 201


class TestAssign:
    def test_assign_requires_valid_user_id(self, alice):
        task_id = create_task(alice).data['id']
        assert alice.post(f'/api/tasks/{task_id}/assign/', {}).status_code == 400
        assert alice.post(
            f'/api/tasks/{task_id}/assign/', {'user_id': 'abc'}
        ).status_code == 400
        assert alice.post(
            f'/api/tasks/{task_id}/assign/', {'user_id': -1}
        ).status_code == 400

    def test_assign_happy_path(self, alice, published):
        task_id = create_task(alice).data['id']
        response = alice.post(f'/api/tasks/{task_id}/assign/', {'user_id': 2})
        assert response.status_code == 200
        assert response.data['status'] == Task.Status.ASSIGNED
        assert response.data['assigned_user_id'] == 2
        assert published[-1]['routing_key'] == 'task_assigned'
        assert published[-1]['body']['assigned_user_id'] == 2


class TestPagination:
    def test_list_is_paginated(self, alice):
        for i in range(3):
            create_task(alice, title=f'task {i}')
        response = alice.get('/api/tasks/')
        assert response.status_code == 200
        assert response.data['count'] == 3
        assert len(response.data['results']) == 3
