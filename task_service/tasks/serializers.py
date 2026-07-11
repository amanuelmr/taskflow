from rest_framework import serializers
from .models import Task


class TaskSerializer(serializers.ModelSerializer):
    class Meta:
        model = Task
        fields = ['id', 'title', 'description', 'owner_id', 'assigned_user_id',
                  'status', 'created_at', 'updated_at']
        read_only_fields = ['id', 'owner_id', 'created_at', 'updated_at']
