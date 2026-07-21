from rest_framework.permissions import BasePermission


class IsSuperAdmin(BasePermission):
    """Permite acceso solo a usuarios con rol 'superadmin'."""

    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.rol == 'superadmin'


class IsDueno(BasePermission):
    """Permite acceso solo a usuarios con rol 'dueno'."""

    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.rol == 'dueno'


class IsRRPP(BasePermission):
    """Permite acceso solo a usuarios con rol 'rrpp'."""

    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.rol == 'rrpp'


class IsGuardia(BasePermission):
    """Permite acceso solo a usuarios con rol 'guardia'."""

    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.rol == 'guardia'


class IsCajera(BasePermission):
    """Permite acceso solo a usuarios con rol 'cajera'."""

    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.rol == 'cajera'
