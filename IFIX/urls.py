from django.contrib import admin
from django.conf import settings
from django.conf.urls.static import static
from django.urls import path, include

from core_views import home

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', home, name='home'),
    path('conta/', include('accounts.urls')),
    path('servicos/', include('services.urls')),
]

urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
