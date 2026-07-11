from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated

from .models import NotificationLog
from .serializers import NotificationLogSerializer


class NotificationLogViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Read-only notification logs. Requires a valid JWT.
    """
    queryset = NotificationLog.objects.all()
    serializer_class = NotificationLogSerializer
    permission_classes = [IsAuthenticated]
