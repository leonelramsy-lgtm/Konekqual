from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from django.core.exceptions import ValidationError
import hashlib
import uuid


class SignalementReseau(models.Model):

    OPERATEURS = [
        ('ORANGE', 'Orange CM'),
        ('MTN', 'MTN CM'),
        ('CAMTEL', 'Camtel'),
        ('NEXTTEL', 'Nexttel'),
        ('YOOMEE', 'Yoomee'),
    ]

    TYPE_RESEAU = [
        ('2G', '2G (Edge)'),
        ('3G', '3G (H+)'),
        ('4G', '4G / LTE'),
        ('5G', '5G'),
        ('FIBRE', 'Fibre optique'),
        ('WIFI', 'Wi-Fi'),
    ]

    VILLES = [
        ('YAOUNDE', 'Yaounde'),
        ('DOUALA', 'Douala'),
        ('BAFOUSSAM', 'Bafoussam'),
        ('BAMENDA', 'Bamenda'),
        ('GAROUA', 'Garoua'),
        ('MAROUA', 'Maroua'),
        ('NGAOUNDERE', 'Ngaoundere'),
        ('BERTOUA', 'Bertoua'),
        ('EBOLOWA', 'Ebolowa'),
        ('BUEA', 'Buea'),
        ('LIMBE', 'Limbe'),
        ('KRIBI', 'Kribi'),
        ('EDEA', 'Edea'),
        ('NKONGSAMBA', 'Nkongsamba'),
        ('FOURAMBAN', 'Fourabam'),
        ('AUTRE', 'Autre ville'),
    ]

    MOMENT_JOURNEE = [
        ('MATIN', 'Matin (6h-12h)'),
        ('APRES_MIDI', 'Apres-midi (12h-18h)'),
        ('SOIR', 'Soir (18h-22h)'),
        ('NUIT', 'Nuit (22h-6h)'),
    ]

    METEO = [
        ('SEC', 'Temps sec'),
        ('PLUIE', 'Pluie legere'),
        ('ORAGE', 'Orage / Forte pluie'),
        ('VENT', 'Vent fort / Harmattan'),
        ('NUAGEUX', 'Nuageux'),
    ]

    operateur = models.CharField(max_length=10, choices=OPERATEURS, verbose_name="Operateur")
    ville = models.CharField(max_length=20, choices=VILLES, verbose_name="Ville")
    quartier = models.CharField(max_length=100, verbose_name="Quartier", help_text="Ex: Bastos, Bonanjo, Obili...")
    type_reseau = models.CharField(max_length=10, choices=TYPE_RESEAU, verbose_name="Type de reseau")

    qualite_appel = models.IntegerField(validators=[MinValueValidator(1), MaxValueValidator(5)], verbose_name="Qualite des appels")
    debit_internet = models.IntegerField(validators=[MinValueValidator(1), MaxValueValidator(5)], verbose_name="Debit internet")
    stabilite = models.IntegerField(validators=[MinValueValidator(1), MaxValueValidator(5)], verbose_name="Stabilite")
    couverture = models.IntegerField(validators=[MinValueValidator(1), MaxValueValidator(5)], verbose_name="Couverture")

    moment_journee = models.CharField(max_length=15, choices=MOMENT_JOURNEE, default='APRES_MIDI', verbose_name="Moment de la journee")
    meteo = models.CharField(max_length=10, choices=METEO, default='SEC', verbose_name="Meteo")
    forfait_prix = models.IntegerField(null=True, blank=True, verbose_name="Prix du forfait (FCFA)")
    commentaire = models.TextField(max_length=500, blank=True, null=True, verbose_name="Commentaire")
    puissance_signal = models.CharField(
        max_length=10,
        blank=True,
        null=True,
        verbose_name="Puissance du signal",
        help_text="Optionnel : RSSI, RSRP, RSRQ"
    )

    modele_telephone = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        verbose_name="Modèle du téléphone",
        help_text="Optionnel : Ex: Samsung A14, iPhone 12..."
    )
    likes = models.IntegerField(default=0, verbose_name="Likes")
    dislikes = models.IntegerField(default=0, verbose_name="Dislikes")

    score_composite = models.FloatField(editable=False, null=True, verbose_name="Score IQR")
    categorie_zone = models.CharField(max_length=30, editable=False, null=True, verbose_name="Categorie de zone")
    ip_address = models.GenericIPAddressField(editable=False, null=True, verbose_name="Adresse IP")
    identifiant_unique = models.CharField(max_length=64, unique=True, editable=False, verbose_name="Identifiant unique")
    date_signalement = models.DateTimeField(auto_now_add=True, verbose_name="Date du signalement")

    def calculer_score_composite(self):
        score = (self.qualite_appel * 0.15 + self.debit_internet * 0.35 + self.stabilite * 0.25 + self.couverture * 0.25) * 20
        return round(score, 1)

    def determiner_categorie(self):
        score = self.score_composite or self.calculer_score_composite()
        if score >= 80: return "Zone d'Excellence"
        elif score >= 60: return "Zone Acceptable"
        elif score >= 40: return "Zone Perfectible"
        else: return "Zone Critique"

    def clean(self):
        super().clean()
        if self.quartier and len(self.quartier.strip()) < 3:
            raise ValidationError({'quartier': 'Le nom du quartier doit contenir au moins 3 caracteres.'})

    def save(self, *args, **kwargs):
        if self.quartier:
            self.quartier = self.quartier.strip().title()
        self.score_composite = self.calculer_score_composite()
        self.categorie_zone = self.determiner_categorie()
        if not self.identifiant_unique:
            raw = f"{self.operateur}-{self.ville}-{self.quartier}-{uuid.uuid4()}"
            self.identifiant_unique = hashlib.sha256(raw.encode()).hexdigest()
        super().save(*args, **kwargs)

    class Meta:
        ordering = ['-date_signalement']
        verbose_name = "Signalement reseau"
        verbose_name_plural = "Signalements reseau"

    def __str__(self):
        return f"{self.get_operateur_display()} - {self.get_ville_display()} - {self.date_signalement:%d/%m/%Y}"


class ContributeurBadge:
    BADGES = [
        (1, 'Nouveau Veilleur', 'Premier signalement'),
        (3, 'Sentinelle', '3 signalements'),
        (5, 'Gardien du Reseau', '5 signalements'),
        (10, 'Expert Connectivite', '10 signalements'),
        (20, 'Maitre des Ondes', '20 signalements'),
        (50, 'Legende du Reseau', '50 signalements'),
        (100, 'Heros National', '100 signalements'),
    ]

    @classmethod
    def get_badge(cls, nb_signalements):
        badge_actuel = None
        for seuil, nom, description in cls.BADGES:
            if nb_signalements >= seuil:
                badge_actuel = {'nom': nom, 'description': description, 'seuil': seuil}
        return badge_actuel

    @classmethod
    def get_prochain_badge(cls, nb_signalements):
        for seuil, nom, description in cls.BADGES:
            if nb_signalements < seuil:
                return {'nom': nom, 'description': description, 'seuil': seuil, 'restant': seuil - nb_signalements}
        return None