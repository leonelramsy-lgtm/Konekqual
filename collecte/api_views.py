from django.http import JsonResponse
from django.db.models import Avg, Count, Max, Min
from .models import SignalementReseau


def api_signalements(request):
    """API : Liste des signalements (avec filtres optionnels)"""
    ville = request.GET.get('ville', '')
    operateur = request.GET.get('operateur', '')
    limite = int(request.GET.get('limite', 50))

    qs = SignalementReseau.objects.all()
    if ville:
        qs = qs.filter(ville=ville.upper())
    if operateur:
        qs = qs.filter(operateur=operateur.upper())

    signalements = qs.values(
        'id', 'operateur', 'ville', 'quartier', 'type_reseau',
        'qualite_appel', 'debit_internet', 'stabilite', 'couverture',
        'score_composite', 'categorie_zone', 'date_signalement',
        'likes', 'dislikes'
    ).order_by('-date_signalement')[:limite]

    return JsonResponse({
        'total': qs.count(),
        'limite': limite,
        'resultats': list(signalements),
    })


def api_stats_globales(request):
    """API : Statistiques globales"""
    stats = SignalementReseau.objects.aggregate(
        nb_total=Count('id'),
        moyenne=Avg('score_composite'),
        meilleure=Max('score_composite'),
        pire=Min('score_composite'),
    )
    return JsonResponse({
        'nb_signalements': stats['nb_total'],
        'score_moyen': round(stats['moyenne'], 1) if stats['moyenne'] else None,
        'meilleur_score': round(stats['meilleure'], 1) if stats['meilleure'] else None,
        'pire_score': round(stats['pire'], 1) if stats['pire'] else None,
    })


def api_par_operateur(request):
    """API : Statistiques par opérateur"""
    data = SignalementReseau.objects.values('operateur').annotate(
        moyenne=Avg('score_composite'),
        nombre=Count('id'),
        appel=Avg('qualite_appel'),
        debit=Avg('debit_internet'),
        stabilite=Avg('stabilite'),
        couverture=Avg('couverture'),
    ).order_by('-moyenne')

    return JsonResponse(list(data), safe=False)


def api_par_ville(request):
    """API : Statistiques par ville"""
    data = SignalementReseau.objects.values('ville').annotate(
        moyenne=Avg('score_composite'),
        nombre=Count('id'),
    ).order_by('-moyenne')

    return JsonResponse(list(data), safe=False)


def api_recommandation(request):
    """API : Recommandation intelligente pour une ville donnée"""
    ville = request.GET.get('ville', 'YAOUNDE')

    # Meilleur opérateur pour cette ville
    meilleur = SignalementReseau.objects.filter(ville=ville.upper()).values('operateur').annotate(
        score=Avg('score_composite'),
        nb=Count('id'),
        appel=Avg('qualite_appel'),
        debit=Avg('debit_internet'),
        stabilite=Avg('stabilite'),
        couverture=Avg('couverture'),
    ).order_by('-score').first()

    if not meilleur:
        return JsonResponse({'erreur': f'Aucune donnee pour {ville}'}, status=404)

    # Pire opérateur
    pire = SignalementReseau.objects.filter(ville=ville.upper()).values('operateur').annotate(
        score=Avg('score_composite')
    ).order_by('score').first()

    return JsonResponse({
        'ville': ville,
        'recommandation': {
            'operateur': meilleur['operateur'],
            'score': round(meilleur['score'], 1),
            'details': {
                'appel': round(meilleur['appel'], 1),
                'debit': round(meilleur['debit'], 1),
                'stabilite': round(meilleur['stabilite'], 1),
                'couverture': round(meilleur['couverture'], 1),
            },
            'nb_signalements': meilleur['nb'],
        },
        'a_eviter': {
            'operateur': pire['operateur'],
            'score': round(pire['score'], 1),
        } if pire and pire['operateur'] != meilleur['operateur'] else None,
    })