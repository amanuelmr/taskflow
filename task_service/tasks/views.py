from django.db import transaction
from django.db.models import Q
from drf_yasg import openapi
from drf_yasg.utils import swagger_auto_schema
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import Task
from .permissions import IsOwner
from .rabbitmq_utils import publish_event
from .serializers import TaskSerializer


class TaskViewSet(viewsets.ModelViewSet):
    """
    CRUD operations for tasks. Users see only tasks they own or are
    assigned to; only the owner can modify a task.
    """
    serializer_class = TaskSerializer
    permission_classes = [IsAuthenticated, IsOwner]

    def get_queryset(self):
        uid = self.request.user.id
        return Task.objects.filter(Q(owner_id=uid) | Q(assigned_user_id=uid))

    def perform_create(self, serializer):
        task = serializer.save(owner_id=self.request.user.id)
        payload = {
            'task_id': task.id,
            'title': task.title,
            'owner_id': task.owner_id,
            'assigned_user_id': task.assigned_user_id,
        }
        transaction.on_commit(
            lambda: publish_event('task_events', 'task_created', payload)
        )

    @swagger_auto_schema(
        method='post',
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            required=['user_id'],
            properties={
                'user_id': openapi.Schema(
                    type=openapi.TYPE_INTEGER,
                    description='ID of the user to assign the task to.',
                )
            },
        ),
        responses={
            200: openapi.Response(
                description="Task assigned successfully.",
                examples={"application/json": {
                    "id": 1, "title": "Task Title",
                    "assigned_user_id": 2, "status": "Assigned",
                }},
            ),
            400: "Bad Request",
            404: "Not Found"
        }
    )
    @action(detail=True, methods=['post'])
    def assign(self, request, pk=None):
        """
        Assign a task to a user. Only the owner can assign.
        """
        task = self.get_object()  # applies queryset filtering + IsOwner

        try:
            user_id = int(request.data.get('user_id'))
        except (TypeError, ValueError):
            user_id = 0
        if user_id <= 0:
            return Response(
                {"detail": "user_id must be a positive integer."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        task.assigned_user_id = user_id
        task.status = Task.Status.ASSIGNED
        task.save(update_fields=['assigned_user_id', 'status', 'updated_at'])

        payload = {
            'task_id': task.id,
            'title': task.title,
            'owner_id': task.owner_id,
            'assigned_user_id': user_id,
        }
        transaction.on_commit(
            lambda: publish_event('task_events', 'task_assigned', payload)
        )

        serializer = self.get_serializer(task)
        return Response(serializer.data, status=status.HTTP_200_OK)
