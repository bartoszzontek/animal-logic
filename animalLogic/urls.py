# animalLogic/urls.py
from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),

    # Mówimy: wszystko co zaczyna się od "api/", szukaj w apps.api.urls
    path('api/', include('apps.api.urls')),

    # Mówimy: cała reszta (strona główna) idzie do apps.core
    path('', include('apps.core.urls')),
]