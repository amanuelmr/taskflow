from django.db.models import Q
from rest_framework import viewsets, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.decorators import action
from rest_framework.response import Response
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi

from .models import Task
from .permissions import IsOwner
from .serializers import TaskSerializer
from .rabbitmq_utils import publish_event


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
        publish_event(
            exchange_name='task_events',
            routing_key='task_created',
            message_body={
                'task_id': task.id,
                'title': task.title,
                'owner_id': task.owner_id,
                'assigned_user_id': task.assigned_user_id,
            }
        )

    @swagger_auto_schema(
        method='post',
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            required=['user_id'],
            properties={
                'user_id': openapi.Schema(type=openapi.TYPE_INTEGER, description='ID of the user to assign the task to.')
            },
        ),
        responses={
            200: openapi.Response(
                description="Task assigned successfully.",
                examples={"application/json": {"id": 1, "title": "Task Title", "assigned_user_id": 2, "status": "Assigned"}}
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

        user_id = request.data.get('user_id')
        if not isinstance(user_id, int) or user_id <= 0:
            return Response(
                {"detail": "user_id must be a positive integer."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        task.assigned_user_id = user_id
        task.status = Task.Status.ASSIGNED
        task.save(update_fields=['assigned_user_id', 'status', 'updated_at'])

        publish_event(
            exchange_name='task_events',
            routing_key='task_assigned',
            message_body={
                'task_id': task.id,
                'title': task.title,
                'owner_id': task.owner_id,
                'assigned_user_id': user_id,
            }
        )

        serializer = self.get_serializer(task)
        return Response(serializer.data, status=status.HTTP_200_OK)
