from django.urls import path

from .views import BolicheDetailView, BolicheMioView, BolichesView, MPCallbackView, MPConnectView

urlpatterns = [
    path('', BolichesView.as_view(), name='boliches-list'),
    path('mio/', BolicheMioView.as_view(), name='boliche-mio'),
    path('<int:pk>/', BolicheDetailView.as_view(), name='boliche-detail'),
    path('mp/connect/', MPConnectView.as_view(), name='mp-connect'),
    path('mp/callback/', MPCallbackView.as_view(), name='mp-callback'),
]
