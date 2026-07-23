from django.urls import path

from .views import (
    CalcularPrecioView,
    EventoCancelarView,
    EventoCreateView,
    EventoDetailView,
    EventoListView,
    MisEventosListView,
)

evento_urlpatterns = [
    path('', EventoListView.as_view(), name='evento-list'),
    path('mios/', MisEventosListView.as_view(), name='evento-mios'),
    path('crear/', EventoCreateView.as_view(), name='evento-create'),
    path('<int:pk>/', EventoDetailView.as_view(), name='evento-detail'),
    path('<int:pk>/cancelar/', EventoCancelarView.as_view(), name='evento-cancelar'),
]

precio_urlpatterns = [
    path('calcular/', CalcularPrecioView.as_view(), name='precio-calcular'),
]
