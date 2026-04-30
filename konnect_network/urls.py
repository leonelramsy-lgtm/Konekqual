from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    # URL d'admin cachée (choisissez ce que vous voulez)
    path('konekqual-admin-2025/', admin.site.urls),

    # Vos URLs publiques
    path('', include('collecte.urls')),
path('admin/', admin.site.urls),
]