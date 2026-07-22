from django.urls import path

from apps.cuentas.views import OrganizadorDetailView, OrganizadorListCreateView

from .views import (
    MetricasAdminView,
    PreferenciaView,
    RankingRRPPView,
    RecaudacionView,
    WalletView,
    WebhookView,
)

pagos_urlpatterns = [
    path('preferencia/', PreferenciaView.as_view(), name='pagos-preferencia'),
    path('webhook/', WebhookView.as_view(), name='pagos-webhook'),
]

wallet_urlpatterns = [
    path('<uuid:token>/', WalletView.as_view(), name='wallet'),
]

dashboard_pagos_urlpatterns = [
    path('recaudacion/<int:evento_id>/', RecaudacionView.as_view(), name='recaudacion'),
    path('ranking-rrpp/<int:evento_id>/', RankingRRPPView.as_view(), name='ranking-rrpp'),
]

admin_urlpatterns = [
    path('metricas/', MetricasAdminView.as_view(), name='admin-metricas'),
    path('organizadores/', OrganizadorListCreateView.as_view(), name='admin-organizadores'),
    path('organizadores/<int:pk>/', OrganizadorDetailView.as_view(), name='admin-organizador-detail'),
]
