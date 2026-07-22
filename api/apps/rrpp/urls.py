from django.urls import path

from .views import (
    AnotarInvitadoView,
    AprobarInvitadoView,
    AsignarEventoView,
    EditarInvitadoView,
    EliminarInvitadoView,
    MiPanelView,
    RechazarInvitadoView,
    RRPPListCreateView,
)

urlpatterns = [
    path('', RRPPListCreateView.as_view(), name='rrpp-list-create'),
    path('<int:pk>/asignar-evento/', AsignarEventoView.as_view(), name='rrpp-asignar-evento'),
    path('mi-panel/', MiPanelView.as_view(), name='rrpp-mi-panel'),
    path('anotar-invitado/', AnotarInvitadoView.as_view(), name='rrpp-anotar-invitado'),
    path('aprobar-invitado/<int:pk>/', AprobarInvitadoView.as_view(), name='rrpp-aprobar-invitado'),
    path('rechazar-invitado/<int:pk>/', RechazarInvitadoView.as_view(), name='rrpp-rechazar-invitado'),
    path('eliminar-invitado/<int:pk>/', EliminarInvitadoView.as_view(), name='rrpp-eliminar-invitado'),
    path('editar-invitado/<int:pk>/', EditarInvitadoView.as_view(), name='rrpp-editar-invitado'),
]
