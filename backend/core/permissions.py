"""Role-based permission classes shared across the API."""
from rest_framework.permissions import BasePermission


class RoleRequired(BasePermission):
    """Allow superusers and users whose role is in `allowed_roles`."""
    allowed_roles = ()
    message = 'Your role does not allow this action.'

    def has_permission(self, request, view):
        user = request.user
        if not (user and user.is_authenticated):
            return False
        if user.is_superuser:
            return True
        return getattr(user, 'role', '') in self.allowed_roles


class IsAdmin(RoleRequired):
    allowed_roles = ('ADMIN',)


class IsAdminOrClerk(RoleRequired):
    allowed_roles = ('ADMIN', 'AP_CLERK')


class IsFinanceOrAdmin(RoleRequired):
    allowed_roles = ('FINANCE', 'ADMIN')


class IsApproverOrAdmin(RoleRequired):
    allowed_roles = ('APPROVER', 'ADMIN', 'FINANCE')
