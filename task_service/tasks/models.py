from django.db import models


class Task(models.Model):
    class Status(models.TextChoices):
        PENDING = 'Pending'
        ASSIGNED = 'Assigned'
        IN_PROGRESS = 'In Progress'
        DONE = 'Done'

    title = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)
    # Cross-service references by id — users live in the user service.
    owner_id = models.IntegerField(db_index=True)
    assigned_user_id = models.IntegerField(null=True, blank=True, db_index=True)
    status = models.CharField(
        max_length=50, choices=Status.choices, default=Status.PENDING, db_index=True
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.title} - {self.status}"
