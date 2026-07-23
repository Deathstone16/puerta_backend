from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView

from .personal_views import PersonalAsignarEventoView, PersonalDetailView, PersonalListCreateView
from .views import LoginView, StaffAsignarEventoView, StaffDetailView, StaffListCreateView

urlpatterns = [
    path('login/',   LoginView.as_view(),       name='login'),
    path('refresh/', TokenRefreshView.as_view(), name='token_refresh'),
]

staff_urlpatterns = [
    path('', StaffListCreateView.as_view(), name='staff-list-create'),
    path('<int:pk>/', StaffDetailView.as_view(), name='staff-detail'),
    path('<int:pk>/asignar-evento/', StaffAsignarEventoView.as_view(), name='staff-asignar-evento'),
]

personal_urlpatterns = [
    path('', PersonalListCreateView.as_view(), name='personal-list-create'),
    path('<int:pk>/', PersonalDetailView.as_view(), name='personal-detail'),
    path('<int:pk>/asignar-evento/', PersonalAsignarEventoView.as_view(), name='personal-asignar-evento'),
]
