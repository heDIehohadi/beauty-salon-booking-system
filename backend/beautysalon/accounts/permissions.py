from rest_framework.permissions import BasePermission


class IsSalonAdmin(BasePermission):
    """
    Allow access only to authenticated salon admins.
    """

    message = "Only salon administrators can access this endpoint."

    def has_permission(self, request, view):
        return (
            request.user
            and request.user.is_authenticated
            and request.user.role == "admin"
        )