from django.conf import settings
from rest_framework.throttling import AnonRateThrottle


class LoginRateThrottle(AnonRateThrottle):
    """5 intentos de login por minuto por IP."""
    scope = 'login'

    def allow_request(self, request, view):
        # Desactivar throttle en tests / debug si no hay rate configurado
        if not self.get_rate():
            return True
        return super().allow_request(request, view)


class WebhookRateThrottle(AnonRateThrottle):
    """60 webhooks por minuto por IP (MP envía ráfagas)."""
    scope = 'webhook'

    def allow_request(self, request, view):
        if not self.get_rate():
            return True
        return super().allow_request(request, view)


class PreferenciaRateThrottle(AnonRateThrottle):
    """10 intentos de crear preferencia por minuto por IP."""
    scope = 'preferencia'

    def allow_request(self, request, view):
        if not self.get_rate():
            return True
        return super().allow_request(request, view)
