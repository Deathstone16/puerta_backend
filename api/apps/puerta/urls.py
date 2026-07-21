from django.urls import path

from .views import (
    AforoView,
    CajeraCobrarListaView,
    CajeraDeshacerView,
    CajeraEscanearWebView,
    CajeraVentaGeneralView,
    GuardiaAprobarView,
    GuardiaEscanearView,
    GuardiaRebotarView,
    ListaAnotarView,
    ListaInfoView,
)

lista_urlpatterns = [
    path('<uuid:slug>/', ListaInfoView.as_view(), name='lista-info'),
    path('<uuid:slug>/anotar/', ListaAnotarView.as_view(), name='lista-anotar'),
]

guardia_urlpatterns = [
    path('escanear/', GuardiaEscanearView.as_view(), name='guardia-escanear'),
    path('aprobar/<int:pk>/', GuardiaAprobarView.as_view(), name='guardia-aprobar'),
    path('rebotar/<int:pk>/', GuardiaRebotarView.as_view(), name='guardia-rebotar'),
]

cajera_urlpatterns = [
    path('escanear-web/<int:pk>/', CajeraEscanearWebView.as_view(), name='cajera-escanear-web'),
    path('cobrar-lista/<int:pk>/', CajeraCobrarListaView.as_view(), name='cajera-cobrar-lista'),
    path('venta-general/', CajeraVentaGeneralView.as_view(), name='cajera-venta-general'),
    path('deshacer/<int:pk>/', CajeraDeshacerView.as_view(), name='cajera-deshacer'),
]

dashboard_urlpatterns = [
    path('aforo/<int:evento_id>/', AforoView.as_view(), name='aforo'),
]
