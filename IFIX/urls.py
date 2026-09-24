from django.contrib import admin
from django.conf import settings
from django.conf.urls.static import static
from django.urls import path, include

from django.contrib.sitemaps.views import sitemap

from core_views import home, privacidade, robots_txt, termos_clientes
from .sitemaps import PaginasSitemap, CategoriasSitemap, ServicosSitemap, CidadesSitemap

SITEMAPS = {
    'paginas': PaginasSitemap, 'categorias': CategoriasSitemap, 'servicos': ServicosSitemap,
    'cidades': CidadesSitemap,
}

admin.site.site_header = '🔧 IFIX · Administração'
admin.site.site_title = 'IFIX Admin'
admin.site.index_title = 'Painel administrativo'

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', home, name='home'),
    path('robots.txt', robots_txt, name='robots_txt'),
    path('privacidade/', privacidade, name='privacidade'),
    path('termos-de-uso/', termos_clientes, name='termos_clientes'),
    path('sitemap.xml', sitemap, {'sitemaps': SITEMAPS}, name='sitemap'),
    path('conta/', include('accounts.urls')),
    path('servicos/', include('services.urls')),
]

urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
