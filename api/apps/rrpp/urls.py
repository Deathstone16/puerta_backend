from django.urls import path

from .views import AnotarInvitadoView, AsignarEventoView, MiPanelView, RRPPListCreateView

urlpatterns = [
    path('', RRPPListCreateView.as_view(), name='rrpp-list-create'),
    path('<int:pk>/asignar-evento/', AsignarEventoView.as_view(), name='rrpp-asignar-evento'),
    path('mi-panel/', MiPanelView.as_view(), name='rrpp-mi-panel'),
    path('anotar-invitado/', AnotarInvitadoView.as_view(), name='rrpp-anotar-invitado'),
]
