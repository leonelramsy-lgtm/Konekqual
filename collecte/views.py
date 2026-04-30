from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.db.models import Avg, Count, Max, Min, StdDev
from django.http import JsonResponse, HttpResponse
from django.utils import timezone
from datetime import timedelta
import json
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
import plotly.utils
import csv
from io import BytesIO

from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.enums import TA_CENTER

from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler

from .models import SignalementReseau, ContributeurBadge
from .forms import SignalementForm

from django.contrib.admin.views.decorators import staff_member_required



# ==========================================
# PAGE D'ACCUEIL
# ==========================================
def accueil(request):
    """Page d'accueil avec choix Public / Admin"""
    return render(request, 'collecte/accueil.html')

def espace_public(request):
    """Page d'accueil pour les utilisateurs publics"""
    nb_total = SignalementReseau.objects.count()
    nb_aujourdhui = SignalementReseau.objects.filter(date_signalement__date=timezone.now().date()).count()
    moyenne = SignalementReseau.objects.aggregate(m=Avg('score_composite'))['m']

    context = {
        'nb_total': nb_total,
        'nb_aujourdhui': nb_aujourdhui,
        'moyenne': round(moyenne, 1) if moyenne else None,
    }
    return render(request, 'collecte/espace_public.html', context)

def carte_view(request):
    """Carte interactive du Cameroun avec les scores reseau par ville"""

    # Coordonnées des villes camerounaises
    coordonnees_villes = {
        'YAOUNDE': {'lat': 3.8480, 'lon': 11.5021, 'nom': 'Yaoundé'},
        'DOUALA': {'lat': 4.0511, 'lon': 9.7679, 'nom': 'Douala'},
        'BAFOUSSAM': {'lat': 5.4778, 'lon': 10.4178, 'nom': 'Bafoussam'},
        'BAMENDA': {'lat': 5.9597, 'lon': 10.1456, 'nom': 'Bamenda'},
        'GAROUA': {'lat': 9.3014, 'lon': 13.3939, 'nom': 'Garoua'},
        'MAROUA': {'lat': 10.5956, 'lon': 14.3247, 'nom': 'Maroua'},
        'NGAOUNDERE': {'lat': 7.3271, 'lon': 13.5833, 'nom': 'Ngaoundéré'},
        'BERTOUA': {'lat': 4.5833, 'lon': 13.6833, 'nom': 'Bertoua'},
        'EBOLOWA': {'lat': 2.9000, 'lon': 11.1500, 'nom': 'Ebolowa'},
        'BUEA': {'lat': 4.1527, 'lon': 9.2410, 'nom': 'Buea'},
        'LIMBE': {'lat': 4.0236, 'lon': 9.2065, 'nom': 'Limbé'},
        'KRIBI': {'lat': 2.9500, 'lon': 9.9167, 'nom': 'Kribi'},
        'EDEA': {'lat': 3.8000, 'lon': 10.1333, 'nom': 'Édéa'},
        'NKONGSAMBA': {'lat': 4.9500, 'lon': 9.9333, 'nom': 'Nkongsamba'},
        'FOURAMBAN': {'lat': 5.7333, 'lon': 10.9000, 'nom': 'Fourabam'},
    }

    # Récupérer les stats par ville
    stats_villes = SignalementReseau.objects.values('ville').annotate(
        score=Avg('score_composite'),
        nb=Count('id'),
        meilleur_op=Max('operateur'),
    )

    # Préparer les données pour la carte
    villes_data = []
    for stat in stats_villes:
        code = stat['ville']
        if code in coordonnees_villes:
            info = coordonnees_villes[code]
            score = stat['score']

            # Déterminer la couleur selon le score
            if score >= 80:
                couleur = '#28a745'  # Vert
                icone = '🟢'
            elif score >= 60:
                couleur = '#ffc107'  # Jaune
                icone = '🟡'
            elif score >= 40:
                couleur = '#ff6600'  # Orange
                icone = '🟠'
            else:
                couleur = '#dc3545'  # Rouge
                icone = '🔴'

            villes_data.append({
                'code': code,
                'nom': info['nom'],
                'lat': info['lat'],
                'lon': info['lon'],
                'score': round(score, 1),
                'nb': stat['nb'],
                'couleur': couleur,
                'icone': icone,
                'meilleur_op': stat.get('meilleur_op', 'N/A'),
            })

    # Données pour le JSON (carte Leaflet)
    villes_json = json.dumps(villes_data)

    return render(request, 'collecte/carte.html', {
        'villes_data': villes_data,
        'villes_json': villes_json,
        'nb_villes': len(villes_data),
    })


def analyse_descriptive(request):
    """Page d'analyse descriptive complète (EC2)"""

    qs = SignalementReseau.objects.all()
    nb = qs.count()

    if nb == 0:
        return render(request, 'collecte/analyse_descriptive.html', {'nb': 0})

    # === STATISTIQUES DE BASE ===
    from django.db.models import StdDev, Variance

    stats_base = qs.aggregate(
        nb=Count('id'),
        moyenne=Avg('score_composite'),
        mediane=Avg('score_composite'),  # Approximation
        ecart_type=StdDev('score_composite'),
        variance=Variance('score_composite'),
        min=Min('score_composite'),
        max=Max('score_composite'),
        moyenne_appel=Avg('qualite_appel'),
        moyenne_debit=Avg('debit_internet'),
        moyenne_stabilite=Avg('stabilite'),
        moyenne_couverture=Avg('couverture'),
        ecart_appel=StdDev('qualite_appel'),
        ecart_debit=StdDev('debit_internet'),
        ecart_stabilite=StdDev('stabilite'),
        ecart_couverture=StdDev('couverture'),
    )

    # Médiane réelle (calculée en Python)
    scores = list(qs.values_list('score_composite', flat=True).order_by('score_composite'))
    n = len(scores)
    if n % 2 == 0:
        mediane = (scores[n // 2 - 1] + scores[n // 2]) / 2
    else:
        mediane = scores[n // 2]

    # Quartiles
    q1 = scores[n // 4] if n >= 4 else scores[0]
    q3 = scores[3 * n // 4] if n >= 4 else scores[-1]

    # === DISTRIBUTION ===
    distribution_categories = {
        'excellence': qs.filter(score_composite__gte=80).count(),
        'acceptable': qs.filter(score_composite__gte=60, score_composite__lt=80).count(),
        'perfectible': qs.filter(score_composite__gte=40, score_composite__lt=60).count(),
        'critique': qs.filter(score_composite__lt=40).count(),
    }

    # Histogramme des scores
    fig_hist = go.Figure(data=[go.Histogram(
        x=scores,
        nbinsx=10,
        marker=dict(color='#0066cc', line=dict(width=1, color='white')),
        hovertemplate='Score: %{x:.0f}<br>Fréquence: %{y}<extra></extra>',
    )])
    fig_hist.update_layout(
        title={'text': '📊 Distribution des scores IQR', 'font': {'size': 14}, 'x': 0.5},
        xaxis_title='Score IQR (/100)',
        yaxis_title='Nombre de signalements',
        plot_bgcolor='rgba(0,0,0,0)',
        paper_bgcolor='rgba(0,0,0,0)',
        font={'family': 'Segoe UI, sans-serif'},
        margin=dict(l=20, r=20, t=50, b=20),
        height=350,
        bargap=0.1,
    )
    hist_json = json.dumps(fig_hist, cls=plotly.utils.PlotlyJSONEncoder)

    # Box plot des 4 critères
    fig_box = go.Figure()
    criteres = ['qualite_appel', 'debit_internet', 'stabilite', 'couverture']
    noms = ['Appels', 'Débit', 'Stabilité', 'Couverture']
    couleurs = ['#ff6600', '#0066cc', '#28a745', '#ffc107']

    for critere, nom, couleur in zip(criteres, noms, couleurs):
        valeurs = list(qs.values_list(critere, flat=True))
        fig_box.add_trace(go.Box(
            y=valeurs,
            name=nom,
            marker=dict(color=couleur),
            boxmean=True,
        ))

    fig_box.update_layout(
        title={'text': '📦 Box plot des critères de qualité', 'font': {'size': 14}, 'x': 0.5},
        yaxis_title='Note (/5)',
        yaxis_range=[0, 6],
        plot_bgcolor='rgba(0,0,0,0)',
        paper_bgcolor='rgba(0,0,0,0)',
        font={'family': 'Segoe UI, sans-serif'},
        margin=dict(l=20, r=20, t=50, b=20),
        height=350,
        showlegend=False,
    )
    box_json = json.dumps(fig_box, cls=plotly.utils.PlotlyJSONEncoder)

    # === CORRÉLATIONS ===
    import pandas as pd
    df = pd.DataFrame(list(qs.values('qualite_appel', 'debit_internet', 'stabilite', 'couverture')))
    corr_matrix = df.corr().round(2)

    fig_corr = go.Figure(data=go.Heatmap(
        z=corr_matrix.values,
        x=['Appels', 'Débit', 'Stabilité', 'Couverture'],
        y=['Appels', 'Débit', 'Stabilité', 'Couverture'],
        colorscale='RdBu_r',
        zmin=-1, zmax=1,
        text=corr_matrix.values,
        texttemplate='%{text}',
        textfont={'size': 12, 'color': 'white'},
        colorbar=dict(title=dict(text='Corrélation', side='right')),
    ))
    fig_corr.update_layout(
        title={'text': '🔗 Matrice de corrélation', 'font': {'size': 14}, 'x': 0.5},
        plot_bgcolor='rgba(0,0,0,0)',
        paper_bgcolor='rgba(0,0,0,0)',
        font={'family': 'Segoe UI, sans-serif'},
        margin=dict(l=20, r=20, t=50, b=20),
        height=350,
    )
    corr_json = json.dumps(fig_corr, cls=plotly.utils.PlotlyJSONEncoder)

    # === VALEURS ABERRANTES ===
    # Méthode IQR (écart interquartile)
    iqr = q3 - q1
    borne_basse = q1 - 1.5 * iqr
    borne_haute = q3 + 1.5 * iqr

    aberrants = qs.filter(
        score_composite__lt=borne_basse
    ) | qs.filter(
        score_composite__gt=borne_haute
    )
    nb_aberrants = aberrants.count()

    context = {
        'nb': nb,
        'stats_base': stats_base,
        'mediane': round(mediane, 1),
        'q1': round(q1, 1),
        'q3': round(q3, 1),
        'iqr': round(iqr, 1),
        'borne_basse': round(borne_basse, 1),
        'borne_haute': round(borne_haute, 1),
        'distribution_categories': distribution_categories,
        'hist_json': hist_json,
        'box_json': box_json,
        'corr_json': corr_json,
        'nb_aberrants': nb_aberrants,
        'aberrants': aberrants.order_by('-date_signalement')[:10],
    }
    return render(request, 'collecte/analyse_descriptive.html', context)

# ==========================================
# FORMULAIRE DE SIGNALEMENT
# ==========================================
def signaler(request):
    if request.method == 'POST':
        form = SignalementForm(request.POST)
        if form.is_valid():
            signalement = form.save(commit=False)
            signalement.ip_address = request.META.get('REMOTE_ADDR', '0.0.0.0')
            signalement.save()
            messages.success(request, f"Signalement #{signalement.id} enregistre avec succes !")
            return redirect('merci', signalement_id=signalement.id)
        else:
            messages.error(request, "Veuillez corriger les erreurs.")
    else:
        form = SignalementForm()
    return render(request, 'collecte/signaler.html', {'form': form})


# ==========================================
# PAGE DE REMERCIEMENT
# ==========================================
def merci(request, signalement_id):
    signalement = get_object_or_404(SignalementReseau, id=signalement_id)
    ip = request.META.get('REMOTE_ADDR', '0.0.0.0')
    nb_contributions = SignalementReseau.objects.filter(ip_address=ip).count()
    badge_actuel = ContributeurBadge.get_badge(nb_contributions)
    prochain_badge = ContributeurBadge.get_prochain_badge(nb_contributions)

    return render(request, 'collecte/merci.html', {
        'signalement': signalement,
        'nb_contributions': nb_contributions,
        'badge_actuel': badge_actuel,
        'prochain_badge': prochain_badge,
    })


# ==========================================
# DASHBOARD
# ==========================================
def dashboard(request):
    filtre_ville = request.GET.get('ville', '')
    filtre_operateur = request.GET.get('operateur', '')
    filtre_periode = request.GET.get('periode', '30')

    qs = SignalementReseau.objects.all()

    if filtre_ville:
        qs = qs.filter(ville=filtre_ville)
    if filtre_operateur:
        qs = qs.filter(operateur=filtre_operateur)
    if filtre_periode and filtre_periode != 'tout':
        jours = int(filtre_periode)
        qs = qs.filter(date_signalement__gte=timezone.now() - timedelta(days=jours))

    nb_filtre = qs.count()

    stats_globales = qs.aggregate(
        nb_total=Count('id'), moyenne=Avg('score_composite'),
        meilleure=Max('score_composite'), pire=Min('score_composite'),
    )
    if stats_globales['moyenne']:
        stats_globales['moyenne'] = round(stats_globales['moyenne'], 1)

    par_operateur = qs.values('operateur').annotate(
        moyenne=Avg('score_composite'), nombre=Count('id')).order_by('-moyenne')

    par_ville = qs.values('ville').annotate(
        moyenne=Avg('score_composite'), nombre=Count('id')).order_by('moyenne')[:10]

    par_type_reseau = qs.values('type_reseau').annotate(
        moyenne=Avg('score_composite'), nombre=Count('id')).order_by('-moyenne')

    zones_critiques = qs.filter(score_composite__lt=40).count()
    zones_excellentes = qs.filter(score_composite__gte=80).count()

    derniers = qs.only('id', 'operateur', 'ville', 'quartier', 'score_composite',
                       'categorie_zone', 'date_signalement', 'likes', 'dislikes').order_by('-date_signalement')[:10]

    # Graphique 1
    graph1_json = None
    if par_operateur:
        ops_labels = [op['operateur'] for op in par_operateur]
        ops_scores = [op['moyenne'] for op in par_operateur]
        couleurs = {'ORANGE': '#ff6600', 'MTN': '#ffcc00', 'CAMTEL': '#0066cc', 'NEXTTEL': '#00cc66',
                    'YOOMEE': '#9933cc'}
        colors = [couleurs.get(op, '#999') for op in ops_labels]
        fig1 = go.Figure(data=[go.Bar(x=ops_labels, y=ops_scores, text=[f"{s:.1f}/100" for s in ops_scores],
                                      textposition='auto', marker_color=colors,
                                      hovertemplate='<b>%{x}</b><br>Score: %{y:.1f}/100<extra></extra>')])
        fig1.update_layout(
            title={'text': 'Score IQR par operateur', 'font': {'size': 16, 'color': '#2c3e50'}, 'x': 0.5},
            yaxis_range=[0, 100], plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)',
            font={'family': 'Segoe UI, sans-serif', 'color': '#2c3e50'}, margin=dict(l=20, r=20, t=50, b=20),
            height=350)
        graph1_json = json.dumps(fig1, cls=plotly.utils.PlotlyJSONEncoder)

    # Graphique 2
    graph2_json = None
    if par_type_reseau:
        labels_t = [t['type_reseau'] for t in par_type_reseau]
        values_t = [t['nombre'] for t in par_type_reseau]
        fig2 = go.Figure(data=[go.Pie(labels=labels_t, values=values_t, hole=0.4,
                                      textinfo='label+percent',
                                      hovertemplate='<b>%{label}</b><br>%{value} signalements<extra></extra>')])
        fig2.update_layout(
            title={'text': 'Repartition par type de reseau', 'font': {'size': 16, 'color': '#2c3e50'}, 'x': 0.5},
            paper_bgcolor='rgba(0,0,0,0)', font={'family': 'Segoe UI, sans-serif', 'color': '#2c3e50'},
            margin=dict(l=20, r=20, t=50, b=20), height=350)
        graph2_json = json.dumps(fig2, cls=plotly.utils.PlotlyJSONEncoder)

    # Graphique 3
    graph3_json = None
    if par_ville:
        v_labels = [v['ville'] for v in par_ville]
        v_scores = [v['moyenne'] for v in par_ville]
        colors_v = ['#dc3545' if s < 40 else '#ffc107' if s < 60 else '#17a2b8' if s < 80 else '#28a745' for s in
                    v_scores]
        fig3 = go.Figure(data=[go.Bar(y=v_labels, x=v_scores, text=[f"{s:.1f}/100" for s in v_scores],
                                      textposition='auto', marker_color=colors_v, orientation='h',
                                      hovertemplate='<b>%{y}</b><br>Score: %{x:.1f}/100<extra></extra>')])
        fig3.update_layout(title={'text': 'Villes a ameliorer', 'font': {'size': 16, 'color': '#2c3e50'}, 'x': 0.5},
                           xaxis_range=[0, 100], plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)',
                           font={'family': 'Segoe UI, sans-serif', 'color': '#2c3e50'},
                           margin=dict(l=20, r=20, t=50, b=20), height=400)
        fig3.update_yaxes(autorange='reversed')
        graph3_json = json.dumps(fig3, cls=plotly.utils.PlotlyJSONEncoder)

    # Graphique 4 : Jauge
    graph4_json = None
    if stats_globales['moyenne']:
        score = stats_globales['moyenne']
        couleur_j = '#28a745' if score >= 80 else '#ffc107' if score >= 60 else '#ff6600' if score >= 40 else '#dc3545'
        fig4 = go.Figure(go.Indicator(mode='gauge+number+delta', value=score,
                                      number={'suffix': '/100', 'font': {'size': 40}},
                                      title={'text': 'Score IQR', 'font': {'size': 14}},
                                      delta={'reference': 50},
                                      gauge={'axis': {'range': [0, 100]}, 'bar': {'color': couleur_j},
                                             'steps': [{'range': [0, 40], 'color': 'rgba(220,53,69,0.2)'},
                                                       {'range': [40, 60], 'color': 'rgba(255,102,0,0.2)'},
                                                       {'range': [60, 80], 'color': 'rgba(255,193,7,0.2)'},
                                                       {'range': [80, 100], 'color': 'rgba(40,167,69,0.2)'}]}))
        fig4.update_layout(paper_bgcolor='rgba(0,0,0,0)', margin=dict(l=20, r=20, t=30, b=20), height=250)
        graph4_json = json.dumps(fig4, cls=plotly.utils.PlotlyJSONEncoder)

    # Graphique 5 : Tendance
    graph5_json = None
    tendance_texte = ""
    jours_tendance = min(int(filtre_periode) if filtre_periode != 'tout' else 30, 30)
    debut = timezone.now() - timedelta(days=jours_tendance)
    tendance_data = qs.filter(date_signalement__gte=debut).extra(
        {'jour': "date(date_signalement)"}).values('jour').annotate(moyenne=Avg('score_composite')).order_by('jour')
    if tendance_data:
        jours_labels = [t['jour'].strftime('%d/%m') if hasattr(t['jour'], 'strftime') else str(t['jour']) for t in
                        tendance_data]
        jours_scores = [t['moyenne'] for t in tendance_data]
        if len(jours_scores) >= 2:
            x = np.arange(len(jours_scores))
            y = np.array(jours_scores)
            a, b = np.polyfit(x, y, 1)
            tendance_line = a * x + b
            tendance_texte = "En amelioration" if a > 0.5 else "En baisse" if a < -0.5 else "Stable"
            couleur_t = '#28a745' if a > 0.5 else '#dc3545' if a < -0.5 else '#ffc107'
        else:
            tendance_line = None
            tendance_texte = "Pas assez de donnees"
            couleur_t = '#6c757d'
        fig5 = go.Figure()
        fig5.add_trace(go.Scatter(x=jours_labels, y=jours_scores, mode='lines+markers', name='Score',
                                  line=dict(color='#0066cc', width=3), marker=dict(size=10)))
        if tendance_line is not None:
            fig5.add_trace(go.Scatter(x=jours_labels, y=tendance_line.tolist(), mode='lines',
                                      name='Tendance', line=dict(color=couleur_t, width=2, dash='dash')))
        fig5.update_layout(
            title={'text': f'Evolution - {tendance_texte}', 'font': {'size': 16, 'color': '#2c3e50'}, 'x': 0.5},
            yaxis_range=[0, 100], plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)',
            font={'family': 'Segoe UI, sans-serif'}, margin=dict(l=20, r=20, t=50, b=20), height=400)
        graph5_json = json.dumps(fig5, cls=plotly.utils.PlotlyJSONEncoder)

    toutes_villes = SignalementReseau.VILLES
    tous_operateurs = SignalementReseau.OPERATEURS

    context = {
        'stats_globales': stats_globales,
        'par_operateur': list(par_operateur),
        'par_ville': list(par_ville),
        'par_type_reseau': list(par_type_reseau),
        'zones_critiques': zones_critiques,
        'zones_excellentes': zones_excellentes,
        'derniers': derniers,
        'graph1_json': graph1_json,
        'graph2_json': graph2_json,
        'graph3_json': graph3_json,
        'graph4_json': graph4_json,
        'graph5_json': graph5_json,
        'tendance_texte': tendance_texte,
        'nb_filtre': nb_filtre,
        'toutes_villes': toutes_villes,
        'tous_operateurs': tous_operateurs,
        'filtre_ville': filtre_ville,
        'filtre_operateur': filtre_operateur,
        'filtre_periode': filtre_periode,
    }
    return render(request, 'collecte/dashboard.html', context)


# ==========================================
# API STATS
# ==========================================
def api_stats(request):
    par_operateur = list(SignalementReseau.objects.values('operateur').annotate(
        moyenne=Avg('score_composite')).order_by('-moyenne'))
    return JsonResponse({'par_operateur': par_operateur}, safe=False)


# ==========================================
# PAGE À PROPOS
# ==========================================
def a_propos(request):
    return render(request, 'collecte/a_propos.html')


# ==========================================
# EXPORT CSV
# ==========================================
def export_csv(request):
    response = HttpResponse(content_type='text/csv; charset=utf-8')
    response['Content-Disposition'] = 'attachment; filename="konekqual_signalements.csv"'
    response.write('\ufeff')

    writer = csv.writer(response, delimiter=';', quoting=csv.QUOTE_MINIMAL)
    writer.writerow([
        'ID', 'Date', 'Operateur', 'Ville', 'Quartier', 'Type reseau',
        'Appel', 'Debit', 'Stabilite', 'Couverture',
        'Score IQR', 'Categorie', 'Moment', 'Meteo', 'Forfait', 'Commentaire'
    ])

    signalements = SignalementReseau.objects.all().order_by('-date_signalement')
    for s in signalements:
        date_str = s.date_signalement.strftime('%d/%m/%Y %H:%M')
        writer.writerow([
            s.id, date_str,
            s.get_operateur_display(), s.get_ville_display(), s.quartier,
            s.get_type_reseau_display(),
            s.qualite_appel, s.debit_internet, s.stabilite, s.couverture,
            s.score_composite, s.categorie_zone,
            s.get_moment_journee_display(), s.get_meteo_display(),
            s.forfait_prix or '', s.commentaire or '',
        ])

    return response


# ==========================================
# EXPORT PDF
# ==========================================
def export_pdf_dashboard(request):
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=2 * cm, leftMargin=2 * cm, topMargin=2 * cm,
                            bottomMargin=2 * cm)
    styles = getSampleStyleSheet()
    titre_style = ParagraphStyle('T', parent=styles['Title'], fontSize=18, textColor=colors.HexColor('#0052a3'),
                                 spaceAfter=0.5 * cm, alignment=TA_CENTER)
    h2_style = ParagraphStyle('H2', parent=styles['Heading2'], fontSize=13, textColor=colors.HexColor('#0052a3'),
                              spaceBefore=0.5 * cm, spaceAfter=0.3 * cm)
    elements = []
    elements.append(Paragraph("KonekQual - Rapport Dashboard", titre_style))
    elements.append(Paragraph(f"Genere le {timezone.now().strftime('%d/%m/%Y a %H:%M')}",
                              ParagraphStyle('D', parent=styles['Normal'], fontSize=8, textColor=colors.grey,
                                             alignment=TA_CENTER, spaceAfter=1 * cm)))

    stats = SignalementReseau.objects.aggregate(nb=Count('id'), moyenne=Avg('score_composite'))
    elements.append(Paragraph("Statistiques", h2_style))
    data = [['Indicateur', 'Valeur'], ['Total signalements', str(stats['nb'] or 0)],
            ['Score IQR moyen', f"{stats['moyenne']:.1f}/100" if stats['moyenne'] else 'N/A']]
    t = Table(data, colWidths=[8 * cm, 6 * cm])
    t.setStyle(TableStyle(
        [('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#0052a3')), ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
         ('FONTSIZE', (0, 0), (-1, -1), 9), ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#cccccc')),
         ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f5f7fa')]),
         ('TOPPADDING', (0, 0), (-1, -1), 6), ('BOTTOMPADDING', (0, 0), (-1, -1), 6)]))
    elements.append(t)
    elements.append(Spacer(1, 0.5 * cm))

    elements.append(Paragraph("Classement par operateur", h2_style))
    par_op = SignalementReseau.objects.values('operateur').annotate(m=Avg('score_composite'), n=Count('id')).order_by(
        '-m')
    data_op = [['Rang', 'Operateur', 'Score', 'Signalements']]
    for i, op in enumerate(par_op, 1):
        data_op.append([str(i), op['operateur'], f"{op['m']:.1f}/100" if op['m'] else 'N/A', str(op['n'])])
    t2 = Table(data_op, colWidths=[2 * cm, 5 * cm, 4 * cm, 4 * cm])
    t2.setStyle(TableStyle(
        [('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#0052a3')), ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
         ('FONTSIZE', (0, 0), (-1, -1), 9), ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#cccccc')),
         ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f5f7fa')]),
         ('TOPPADDING', (0, 0), (-1, -1), 6), ('BOTTOMPADDING', (0, 0), (-1, -1), 6)]))
    elements.append(t2)
    elements.append(Spacer(1, 1 * cm))
    elements.append(Paragraph("KonekQual",
                              ParagraphStyle('F', parent=styles['Normal'], fontSize=7, textColor=colors.grey,
                                             alignment=TA_CENTER)))
    doc.build(elements)
    buffer.seek(0)
    response = HttpResponse(buffer, content_type='application/pdf')
    response['Content-Disposition'] = 'attachment; filename="dashboard.pdf"'
    return response


def export_pdf_heatmap(request):
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=2 * cm, leftMargin=2 * cm, topMargin=2 * cm,
                            bottomMargin=2 * cm)
    styles = getSampleStyleSheet()
    titre_style = ParagraphStyle('T', parent=styles['Title'], fontSize=18, textColor=colors.HexColor('#0052a3'),
                                 spaceAfter=0.5 * cm, alignment=TA_CENTER)
    h2_style = ParagraphStyle('H2', parent=styles['Heading2'], fontSize=13, textColor=colors.HexColor('#0052a3'),
                              spaceBefore=0.5 * cm, spaceAfter=0.3 * cm)
    elements = []
    elements.append(Paragraph("KonekQual - Rapport Heatmap", titre_style))
    elements.append(Paragraph(f"Genere le {timezone.now().strftime('%d/%m/%Y a %H:%M')}",
                              ParagraphStyle('D', parent=styles['Normal'], fontSize=8, textColor=colors.grey,
                                             alignment=TA_CENTER, spaceAfter=1 * cm)))

    elements.append(Paragraph("Meilleur operateur par ville", h2_style))
    data = [['Ville', 'Meilleur operateur', 'Score IQR']]
    for ville in SignalementReseau.VILLES:
        meilleur = SignalementReseau.objects.filter(ville=ville[0]).values('operateur').annotate(
            m=Avg('score_composite')).order_by('-m').first()
        if meilleur:
            data.append([ville[1], dict(SignalementReseau.OPERATEURS).get(meilleur['operateur'], ''),
                         f"{meilleur['m']:.0f}/100"])
    t = Table(data, colWidths=[5 * cm, 6 * cm, 4 * cm])
    t.setStyle(TableStyle(
        [('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#0052a3')), ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
         ('FONTSIZE', (0, 0), (-1, -1), 9), ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#cccccc')),
         ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f5f7fa')]),
         ('TOPPADDING', (0, 0), (-1, -1), 6), ('BOTTOMPADDING', (0, 0), (-1, -1), 6)]))
    elements.append(t)
    elements.append(Spacer(1, 1 * cm))
    elements.append(Paragraph("KonekQual",
                              ParagraphStyle('F', parent=styles['Normal'], fontSize=7, textColor=colors.grey,
                                             alignment=TA_CENTER)))
    doc.build(elements)
    buffer.seek(0)
    response = HttpResponse(buffer, content_type='application/pdf')
    response['Content-Disposition'] = 'attachment; filename="heatmap.pdf"'
    return response


def export_pdf_clustering(request):
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=2 * cm, leftMargin=2 * cm, topMargin=2 * cm,
                            bottomMargin=2 * cm)
    styles = getSampleStyleSheet()
    titre_style = ParagraphStyle('T', parent=styles['Title'], fontSize=18, textColor=colors.HexColor('#0052a3'),
                                 spaceAfter=0.5 * cm, alignment=TA_CENTER)
    h2_style = ParagraphStyle('H2', parent=styles['Heading2'], fontSize=13, textColor=colors.HexColor('#0052a3'),
                              spaceBefore=0.5 * cm, spaceAfter=0.3 * cm)
    elements = []
    elements.append(Paragraph("KonekQual - Rapport Clustering", titre_style))
    elements.append(Paragraph(f"Genere le {timezone.now().strftime('%d/%m/%Y a %H:%M')}",
                              ParagraphStyle('D', parent=styles['Normal'], fontSize=8, textColor=colors.grey,
                                             alignment=TA_CENTER, spaceAfter=1 * cm)))

    signalements = SignalementReseau.objects.all()
    if signalements.count() >= 6:
        X = np.array([[s.qualite_appel, s.debit_internet, s.stabilite, s.couverture] for s in signalements])
        scaler = StandardScaler()
        kmeans = KMeans(n_clusters=3, random_state=42, n_init=10)
        labels = kmeans.fit_predict(scaler.fit_transform(X))
        clusters = []
        for i in range(3):
            cd = X[labels == i]
            m = cd.mean(axis=0)
            sm = m.mean() * 20
            nom = "Excellence" if sm >= 70 else "Intermediaire" if sm >= 45 else "Critique"
            clusters.append(
                {'nom': nom, 'taille': len(cd), 'pct': round(len(cd) / len(X) * 100, 1), 'appel': round(m[0], 1),
                 'debit': round(m[1], 1), 'stab': round(m[2], 1), 'couv': round(m[3], 1), 'score': round(sm, 1)})
        clusters.sort(key=lambda x: x['score'], reverse=True)

        elements.append(Paragraph("Groupes K-Means", h2_style))
        data = [['Groupe', 'Effectif', '%', 'Appel', 'Debit', 'Stabilite', 'Couverture', 'Score']]
        for c in clusters:
            data.append(
                [c['nom'], str(c['taille']), f"{c['pct']}%", f"{c['appel']}/5", f"{c['debit']}/5", f"{c['stab']}/5",
                 f"{c['couv']}/5", f"{c['score']}/100"])
        t = Table(data, colWidths=[3 * cm, 1.5 * cm, 1.5 * cm, 1.5 * cm, 1.5 * cm, 1.5 * cm, 1.5 * cm, 2 * cm])
        t.setStyle(TableStyle(
            [('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#0052a3')), ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
             ('FONTSIZE', (0, 0), (-1, -1), 8), ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#cccccc')),
             ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f5f7fa')]),
             ('TOPPADDING', (0, 0), (-1, -1), 4), ('BOTTOMPADDING', (0, 0), (-1, -1), 4)]))
        elements.append(t)
    elements.append(Spacer(1, 1 * cm))
    elements.append(Paragraph("KonekQual",
                              ParagraphStyle('F', parent=styles['Normal'], fontSize=7, textColor=colors.grey,
                                             alignment=TA_CENTER)))
    doc.build(elements)
    buffer.seek(0)
    response = HttpResponse(buffer, content_type='application/pdf')
    response['Content-Disposition'] = 'attachment; filename="clustering.pdf"'
    return response


def export_pdf_analyse(request):
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=2*cm, leftMargin=2*cm, topMargin=2*cm, bottomMargin=2*cm)
    styles = getSampleStyleSheet()
    titre_style = ParagraphStyle('T', parent=styles['Title'], fontSize=18, textColor=colors.HexColor('#0052a3'), spaceAfter=0.5*cm, alignment=TA_CENTER)
    h2_style = ParagraphStyle('H2', parent=styles['Heading2'], fontSize=13, textColor=colors.HexColor('#0052a3'), spaceBefore=0.5*cm, spaceAfter=0.3*cm)
    elements = []
    elements.append(Paragraph("KonekQual - Analyse Descriptive", titre_style))
    elements.append(Paragraph(f"Genere le {timezone.now().strftime('%d/%m/%Y a %H:%M')}", ParagraphStyle('D', parent=styles['Normal'], fontSize=8, textColor=colors.grey, alignment=TA_CENTER, spaceAfter=1*cm)))
    
    from django.db.models import StdDev
    stats = SignalementReseau.objects.aggregate(nb=Count('id'), moyenne=Avg('score_composite'), ecart=StdDev('score_composite'), min=Min('score_composite'), max=Max('score_composite'))
    elements.append(Paragraph("Statistiques descriptives", h2_style))
    data = [['Indicateur','Valeur'],['Effectif',str(stats['nb'] or 0)],['Moyenne',f"{stats['moyenne']:.1f}/100" if stats['moyenne'] else 'N/A'],['Ecart-type',f"{stats['ecart']:.1f}" if stats['ecart'] else 'N/A'],['Minimum',f"{stats['min']:.1f}/100" if stats['min'] else 'N/A'],['Maximum',f"{stats['max']:.1f}/100" if stats['max'] else 'N/A']]
    t = Table(data, colWidths=[8*cm,6*cm])
    t.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),colors.HexColor('#0052a3')),('TEXTCOLOR',(0,0),(-1,0),colors.white),('FONTSIZE',(0,0),(-1,-1),9),('GRID',(0,0),(-1,-1),0.5,colors.HexColor('#cccccc')),('ROWBACKGROUNDS',(0,1),(-1,-1),[colors.white,colors.HexColor('#f5f7fa')]),('TOPPADDING',(0,0),(-1,-1),6),('BOTTOMPADDING',(0,0),(-1,-1),6)]))
    elements.append(t)
    elements.append(Spacer(1,1*cm))
    elements.append(Paragraph("KonekQual", ParagraphStyle('F', parent=styles['Normal'], fontSize=7, textColor=colors.grey, alignment=TA_CENTER)))
    doc.build(elements)
    buffer.seek(0)
    response = HttpResponse(buffer, content_type='application/pdf')
    response['Content-Disposition'] = 'attachment; filename="analyse.pdf"'
    return response

def export_pdf_carte(request):
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=2 * cm, leftMargin=2 * cm, topMargin=2 * cm,
                            bottomMargin=2 * cm)
    styles = getSampleStyleSheet()
    titre_style = ParagraphStyle('T', parent=styles['Title'], fontSize=18, textColor=colors.HexColor('#0052a3'),
                                 spaceAfter=0.5 * cm, alignment=TA_CENTER)
    h2_style = ParagraphStyle('H2', parent=styles['Heading2'], fontSize=13, textColor=colors.HexColor('#0052a3'),
                              spaceBefore=0.5 * cm, spaceAfter=0.3 * cm)
    elements = []
    elements.append(Paragraph("KonekQual - Carte des Villes", titre_style))
    elements.append(Paragraph(f"Genere le {timezone.now().strftime('%d/%m/%Y a %H:%M')}",
                              ParagraphStyle('D', parent=styles['Normal'], fontSize=8, textColor=colors.grey,
                                             alignment=TA_CENTER, spaceAfter=1 * cm)))

    elements.append(Paragraph("Scores par ville", h2_style))
    data = [['Ville', 'Score IQR', 'Signalements', 'Statut']]
    for ville in SignalementReseau.VILLES:
        st = SignalementReseau.objects.filter(ville=ville[0]).aggregate(m=Avg('score_composite'), n=Count('id'))
        if st['n'] > 0:
            s = st['m']
            statut = 'Excellence' if s >= 80 else 'Bon' if s >= 60 else 'Moyen' if s >= 40 else 'Critique'
            data.append([ville[1], f"{s:.0f}/100", str(st['n']), statut])
    t = Table(data, colWidths=[5 * cm, 3 * cm, 3 * cm, 4 * cm])
    t.setStyle(TableStyle(
        [('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#0052a3')), ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
         ('FONTSIZE', (0, 0), (-1, -1), 9), ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#cccccc')),
         ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f5f7fa')]),
         ('TOPPADDING', (0, 0), (-1, -1), 6), ('BOTTOMPADDING', (0, 0), (-1, -1), 6)]))
    elements.append(t)
    elements.append(Spacer(1, 1 * cm))
    elements.append(Paragraph("KonekQual",
                              ParagraphStyle('F', parent=styles['Normal'], fontSize=7, textColor=colors.grey,
                                             alignment=TA_CENTER)))
    doc.build(elements)
    buffer.seek(0)
    response = HttpResponse(buffer, content_type='application/pdf')
    response['Content-Disposition'] = 'attachment; filename="carte.pdf"'
    return response

# ==========================================
# COMPARATEUR D'OPÉRATEURS
# ==========================================
def comparer_operateurs(request):
    operateur1 = request.GET.get('op1', 'ORANGE')
    operateur2 = request.GET.get('op2', 'MTN')
    all_operateurs = SignalementReseau.OPERATEURS

    def get_stats(op):
        data = SignalementReseau.objects.filter(operateur=op)
        nb = data.count()
        if nb == 0:
            return None
        stats = data.aggregate(
            moyenne=Avg('score_composite'), appel=Avg('qualite_appel'),
            debit=Avg('debit_internet'), stabilite=Avg('stabilite'),
            couverture=Avg('couverture'), max_score=Max('score_composite'), min_score=Min('score_composite'))
        meilleure_ville = data.values('ville').annotate(m=Avg('score_composite')).order_by('-m').first()
        pire_ville = data.values('ville').annotate(m=Avg('score_composite')).order_by('m').first()
        excellent = data.filter(score_composite__gte=80).count()
        acceptable = data.filter(score_composite__gte=60, score_composite__lt=80).count()
        perfectible = data.filter(score_composite__gte=40, score_composite__lt=60).count()
        critique = data.filter(score_composite__lt=40).count()
        prix_moyen = data.filter(forfait_prix__isnull=False).aggregate(p=Avg('forfait_prix'))['p']
        return {
            'nb': nb, 'moyenne': round(stats['moyenne'], 1) if stats['moyenne'] else None,
            'appel': round(stats['appel'], 1) if stats['appel'] else None,
            'debit': round(stats['debit'], 1) if stats['debit'] else None,
            'stabilite': round(stats['stabilite'], 1) if stats['stabilite'] else None,
            'couverture': round(stats['couverture'], 1) if stats['couverture'] else None,
            'max_score': round(stats['max_score'], 1) if stats['max_score'] else None,
            'min_score': round(stats['min_score'], 1) if stats['min_score'] else None,
            'meilleure_ville': meilleure_ville, 'pire_ville': pire_ville,
            'excellent': excellent, 'acceptable': acceptable, 'perfectible': perfectible, 'critique': critique,
            'prix_moyen': round(prix_moyen) if prix_moyen else None,
        }

    stats1 = get_stats(operateur1)
    stats2 = get_stats(operateur2)

    graph_json = None
    if stats1 and stats2:
        categories = ['Appels', 'Debit', 'Stabilite', 'Couverture', 'Score IQR']
        fig = go.Figure()
        fig.add_trace(go.Scatterpolar(
            r=[stats1['appel'] or 0, stats1['debit'] or 0, stats1['stabilite'] or 0,
               stats1['couverture'] or 0, stats1['moyenne'] / 20 if stats1['moyenne'] else 0],
            theta=categories, fill='toself', name=dict(all_operateurs)[operateur1],
            marker=dict(color='rgba(255,102,0,0.7)'), line=dict(color='#ff6600', width=2)))
        fig.add_trace(go.Scatterpolar(
            r=[stats2['appel'] or 0, stats2['debit'] or 0, stats2['stabilite'] or 0,
               stats2['couverture'] or 0, stats2['moyenne'] / 20 if stats2['moyenne'] else 0],
            theta=categories, fill='toself', name=dict(all_operateurs)[operateur2],
            marker=dict(color='rgba(0,102,204,0.7)'), line=dict(color='#0066cc', width=2)))
        fig.update_layout(title={'text': 'Comparaison radar', 'font': {'size': 14}, 'x': 0.5},
                          polar=dict(radialaxis=dict(range=[0, 5])), paper_bgcolor='rgba(0,0,0,0)',
                          font={'family': 'Segoe UI, sans-serif'}, margin=dict(l=40, r=40, t=50, b=40),
                          height=400, legend=dict(orientation='h', y=1.15))
        graph_json = json.dumps(fig, cls=plotly.utils.PlotlyJSONEncoder)

    context = {
        'all_operateurs': all_operateurs, 'operateur1': operateur1, 'operateur2': operateur2,
        'stats1': stats1, 'stats2': stats2,
        'nom1': dict(all_operateurs).get(operateur1, operateur1),
        'nom2': dict(all_operateurs).get(operateur2, operateur2),
        'graph_json': graph_json,
    }
    return render(request, 'collecte/comparer.html', context)


# ==========================================
# CLUSTERING K-MEANS
# ==========================================
def clustering_view(request):
    signalements = SignalementReseau.objects.all()
    nb_total = signalements.count()
    clusters = []

    if nb_total >= 6:
        data = []
        for s in signalements:
            data.append([s.qualite_appel, s.debit_internet, s.stabilite, s.couverture])
        X = np.array(data)
        scaler = StandardScaler()
        X_scaled = scaler.fit_transform(X)
        kmeans = KMeans(n_clusters=3, random_state=42, n_init=10)
        kmeans.fit(X_scaled)
        labels = kmeans.labels_

        for i in range(3):
            cluster_data = X[labels == i]
            moyenne = cluster_data.mean(axis=0)
            taille = len(cluster_data)
            score_moyen = moyenne.mean() * 20
            if score_moyen >= 70:
                nom, icone = "Groupe Excellence", "🟢"
            elif score_moyen >= 45:
                nom, icone = "Groupe Intermediaire", "🟡"
            else:
                nom, icone = "Groupe Critique", "🔴"
            clusters.append({
                'nom': nom, 'icone': icone, 'taille': taille,
                'pourcentage': round(taille / nb_total * 100, 1),
                'appel_moyen': round(moyenne[0], 1), 'debit_moyen': round(moyenne[1], 1),
                'stabilite_moyenne': round(moyenne[2], 1), 'couverture_moyenne': round(moyenne[3], 1),
                'score_moyen': round(score_moyen, 1),
            })
        clusters.sort(key=lambda x: x['score_moyen'], reverse=True)

        fig = go.Figure()
        couleurs_clusters = ['#28a745', '#ffc107', '#dc3545']
        noms_clusters = [c['nom'] for c in clusters]
        for i in range(3):
            cluster_mask = labels == i
            fig.add_trace(go.Scatter(
                x=X[cluster_mask, 2], y=X[cluster_mask, 3], mode='markers',
                name=noms_clusters[i],
                marker=dict(size=12, color=couleurs_clusters[i], opacity=0.7, line=dict(width=1, color='white')),
                text=[f"Score: {X[j].mean() * 20:.0f}/100" for j in range(len(X)) if cluster_mask[j]],
                hovertemplate='<b>%{text}</b><extra></extra>'))
        fig.update_layout(title={'text': 'Classification non-supervisee (K-Means)', 'font': {'size': 16}},
                          xaxis_title='Stabilite (/5)', yaxis_title='Couverture (/5)',
                          plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)',
                          font={'family': 'Segoe UI, sans-serif'}, margin=dict(l=20, r=20, t=50, b=20),
                          height=400, legend=dict(orientation='h', y=1.12))
        clustering_graph = json.dumps(fig, cls=plotly.utils.PlotlyJSONEncoder)
    else:
        clustering_graph = None

    return render(request, 'collecte/clustering.html', {
        'clusters': clusters, 'clustering_graph': clustering_graph, 'nb_total': nb_total,
    })


# ==========================================
# LIKE / DISLIKE
# ==========================================
def like_signalement(request, signalement_id):
    if request.method == 'POST':
        signalement = get_object_or_404(SignalementReseau, id=signalement_id)
        signalement.likes += 1
        signalement.save()
        return JsonResponse({'likes': signalement.likes, 'dislikes': signalement.dislikes})
    return JsonResponse({'error': 'Methode non autorisee'}, status=405)


def dislike_signalement(request, signalement_id):
    if request.method == 'POST':
        signalement = get_object_or_404(SignalementReseau, id=signalement_id)
        signalement.dislikes += 1
        signalement.save()
        return JsonResponse({'likes': signalement.likes, 'dislikes': signalement.dislikes})
    return JsonResponse({'error': 'Methode non autorisee'}, status=405)

def modifier_signalement(request, signalement_id):
    signalement = get_object_or_404(SignalementReseau, id=signalement_id)
    if request.method == 'POST':
        form = SignalementForm(request.POST, instance=signalement)
        if form.is_valid():
            form.save()
            messages.success(request, "Signalement modifié avec succès !")
            return redirect('dashboard')
    else:
        form = SignalementForm(instance=signalement)
    return render(request, 'collecte/modifier.html', {'form': form, 'signalement': signalement})

def supprimer_signalement(request, signalement_id):
    signalement = get_object_or_404(SignalementReseau, id=signalement_id)
    if request.method == 'POST':
        signalement.delete()
        messages.success(request, "Signalement supprimé.")
        return redirect('dashboard')
    return render(request, 'collecte/supprimer.html', {'signalement': signalement})
# ==========================================
# HEATMAP
# ==========================================
def heatmap_view(request):
    data = SignalementReseau.objects.values('ville', 'operateur').annotate(
        moyenne=Avg('score_composite'), nombre=Count('id')).order_by('ville', '-moyenne')

    operateurs_list = list(SignalementReseau.OPERATEURS)
    villes_list = list(SignalementReseau.VILLES)
    operateurs_labels = [op[1] for op in operateurs_list]
    villes_labels = [v[1] for v in villes_list]

    matrice = []
    annotations = []

    for i, ville in enumerate(villes_list):
        ligne = []
        for j, op in enumerate(operateurs_list):
            score = None
            nb = 0
            for d in data:
                if d['ville'] == ville[0] and d['operateur'] == op[0]:
                    score = d['moyenne']
                    nb = d['nombre']
                    break
            if score is not None:
                ligne.append(round(score, 1))
                annotations.append({
                    'x': operateurs_labels[j],
                    'y': villes_labels[i],
                    'text': f"<b>{score:.0f}</b>",
                    'showarrow': False,
                    'font': {'color': 'white' if score < 40 or score > 70 else '#1a1a2e', 'size': 11, 'family': 'Arial, sans-serif'},
                })
            else:
                ligne.append(None)
                annotations.append({
                    'x': operateurs_labels[j],
                    'y': villes_labels[i],
                    'text': 'N/A',
                    'showarrow': False,
                    'font': {'color': '#999', 'size': 9},
                })
        matrice.append(ligne)

    fig = go.Figure(data=go.Heatmap(
        z=matrice,
        x=operateurs_labels,
        y=villes_labels,
        colorscale=[[0, '#dc3545'], [0.25, '#ff6600'], [0.5, '#ffc107'], [0.75, '#17a2b8'], [1, '#28a745']],
        zmin=0, zmax=100,
        hoverinfo='text',
        hovertext=[[f"<b>{v[1]}</b><br>{op[1]}<br>Score: {score:.0f}/100" if score is not None else f"<b>{v[1]}</b><br>{op[1]}<br>N/A" for op, score in zip(operateurs_list, ligne)] for v, ligne in zip(villes_list, matrice)],
        colorbar=dict(title=dict(text='Score IQR', side='right', font=dict(size=11)), tickfont=dict(size=10)),
        xgap=2, ygap=2,
    ))

    fig.update_layout(
        title={'text': 'Qualite reseau • Ville × Operateur', 'font': {'size': 16, 'color': '#333'}, 'x': 0.5},
        xaxis={'title': '', 'side': 'top', 'tickfont': {'size': 10, 'color': '#555'}},
        yaxis={'title': '', 'tickfont': {'size': 10, 'color': '#555'}},
        plot_bgcolor='#fafafa',
        paper_bgcolor='rgba(0,0,0,0)',
        font={'family': 'Segoe UI, Arial, sans-serif', 'size': 11},
        margin=dict(l=20, r=20, t=50, b=20),
        height=450 + len(villes_labels) * 8,
        annotations=annotations,
    )

    heatmap_json = json.dumps(fig, cls=plotly.utils.PlotlyJSONEncoder)

    meilleurs_par_ville = []
    for ville in villes_list:
        meilleur = None
        for d in data:
            if d['ville'] == ville[0]:
                if meilleur is None or d['moyenne'] > meilleur['moyenne']:
                    meilleur = d
        if meilleur:
            meilleurs_par_ville.append({
                'ville': ville[1],
                'operateur': dict(operateurs_list).get(meilleur['operateur'], meilleur['operateur']),
                'score': round(meilleur['moyenne'], 0),
            })

    return render(request, 'collecte/heatmap.html', {
        'heatmap_json': heatmap_json,
        'meilleurs_par_ville': meilleurs_par_ville,
    })

# ==========================================
# PAGES D'ERREUR
# ==========================================
def handler404(request, exception):
    return render(request, 'collecte/404.html', status=404)


def handler500(request):
    return render(request, 'collecte/500.html', status=500)
