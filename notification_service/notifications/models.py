from django.db import models


class NotificationLog(models.Model):
    event_type = models.CharField(max_length=100)
    payload = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.event_type} - {self.created_at}"
