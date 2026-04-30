from django.urls import path
from . import views, api_views

urlpatterns = [
    # Pages principales
    path('', views.accueil, name='accueil'),
    path('signaler/', views.signaler, name='signaler'),
    path('merci/<int:signalement_id>/', views.merci, name='merci'),
    path('dashboard/', views.dashboard, name='dashboard'),
    path('a-propos/', views.a_propos, name='a_propos'),

    # Fonctionnalités
    path('comparer/', views.comparer_operateurs, name='comparer'),
    path('clustering/', views.clustering_view, name='clustering'),
    path('heatmap/', views.heatmap_view, name='heatmap'),

    # Like / Dislike
    path('like/<int:signalement_id>/', views.like_signalement, name='like_signalement'),
    path('dislike/<int:signalement_id>/', views.dislike_signalement, name='dislike_signalement'),

    # Exports
    path('export-csv/', views.export_csv, name='export_csv'),

    # API Interne
    path('api/stats/', views.api_stats, name='api_stats'),

    # API REST Publique
    path('api/signalements/', api_views.api_signalements, name='api_signalements'),
    path('api/stats-globales/', api_views.api_stats_globales, name='api_stats_globales'),
    path('api/par-operateur/', api_views.api_par_operateur, name='api_par_operateur'),
    path('api/par-ville/', api_views.api_par_ville, name='api_par_ville'),
    path('api/recommandation/', api_views.api_recommandation, name='api_recommandation'),

path('carte/', views.carte_view, name='carte'),
path('analyse-descriptive/', views.analyse_descriptive, name='analyse_descriptive'),

path('modifier/<int:signalement_id>/', views.modifier_signalement, name='modifier'),
path('supprimer/<int:signalement_id>/', views.supprimer_signalement, name='supprimer'),

path('export-pdf-dashboard/', views.export_pdf_dashboard, name='export_pdf_dashboard'),
path('export-pdf-heatmap/', views.export_pdf_heatmap, name='export_pdf_heatmap'),
path('export-pdf-clustering/', views.export_pdf_clustering, name='export_pdf_clustering'),
path('export-pdf-analyse/', views.export_pdf_analyse, name='export_pdf_analyse'),
path('export-pdf-carte/', views.export_pdf_carte, name='export_pdf_carte'),
path('espace-public/', views.espace_public, name='espace_public'),
]