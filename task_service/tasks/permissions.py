from rest_framework import permissions


class IsOwner(permissions.BasePermission):
    """Write access is limited to the task's owner; assignees may read."""

    def has_object_permission(self, request, view, obj):
        if request.method in permissions.SAFE_METHODS:
            return obj.owner_id == request.user.id or obj.assigned_user_id == request.user.id
        return obj.owner_id == request.user.id
