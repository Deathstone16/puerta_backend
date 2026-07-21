from django.conf import settings
from django.contrib import admin
from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

from apps.eventos.urls import evento_urlpatterns, precio_urlpatterns
from apps.pagos.urls import (
    admin_urlpatterns,
    dashboard_pagos_urlpatterns,
    pagos_urlpatterns,
    wallet_urlpatterns,
)
from apps.puerta.urls import (
    cajera_urlpatterns,
    dashboard_urlpatterns,
    guardia_urlpatterns,
    lista_urlpatterns,
)

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/auth/', include('apps.cuentas.urls')),
    path('api/boliches/', include('apps.boliches.urls')),
    path('api/eventos/', include(evento_urlpatterns)),
    path('api/precios/', include(precio_urlpatterns)),
    path('api/rrpp/', include('apps.rrpp.urls')),
    path('api/lista/', include(lista_urlpatterns)),
    path('api/puerta/guardia/', include(guardia_urlpatterns)),
    path('api/puerta/cajera/', include(cajera_urlpatterns)),
    path('api/pagos/', include(pagos_urlpatterns)),
    path('api/wallet/', include(wallet_urlpatterns)),
    path('api/dashboard/', include(dashboard_urlpatterns + dashboard_pagos_urlpatterns)),
    path('api/admin/', include(admin_urlpatterns)),
]

# Swagger/OpenAPI solo en desarrollo
if settings.DEBUG:
    urlpatterns += [
        path('api/schema/', SpectacularAPIView.as_view(), name='schema'),
        path('api/schema/swagger-ui/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),
    ]
