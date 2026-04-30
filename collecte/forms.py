from django import forms
from .models import SignalementReseau


class SignalementForm(forms.ModelForm):
    """Formulaire de collecte de signalement réseau"""

    class Meta:
        model = SignalementReseau
        fields = [
            'operateur', 'ville', 'quartier', 'type_reseau',
            'qualite_appel', 'debit_internet', 'stabilite', 'couverture',
            'moment_journee', 'meteo', 'forfait_prix', 'commentaire',
            'puissance_signal', 'modele_telephone',
        ]

        widgets = {
            'operateur': forms.RadioSelect(attrs={'class': 'operateur-radio'}),
            'ville': forms.Select(attrs={'class': 'form-select'}),
            'quartier': forms.TextInput(attrs={
                'class': 'form-input',
                'placeholder': 'Ex: Bastos, Bonanjo, Obili...',
                'autocomplete': 'off',
            }),
            'type_reseau': forms.Select(attrs={'class': 'form-select'}),
            'qualite_appel': forms.NumberInput(attrs={
                'class': 'star-input',
                'min': 1, 'max': 5,
                'placeholder': '1-5',
            }),
            'debit_internet': forms.NumberInput(attrs={
                'class': 'star-input',
                'min': 1, 'max': 5,
                'placeholder': '1-5',
            }),
            'stabilite': forms.NumberInput(attrs={
                'class': 'star-input',
                'min': 1, 'max': 5,
                'placeholder': '1-5',
            }),
            'couverture': forms.NumberInput(attrs={
                'class': 'star-input',
                'min': 1, 'max': 5,
                'placeholder': '1-5',
            }),
            'moment_journee': forms.RadioSelect(attrs={'class': 'moment-radio'}),
            'meteo': forms.RadioSelect(attrs={'class': 'meteo-radio'}),
            'forfait_prix': forms.NumberInput(attrs={
                'class': 'form-input',
                'placeholder': 'Ex: 5000',
                'min': 0,
            }),
            'commentaire': forms.Textarea(attrs={
                'class': 'form-textarea',
                'rows': 3,
                'placeholder': 'Decrivez votre experience...',
                'maxlength': 500,
            }),
            'puissance_signal': forms.TextInput(attrs={
                'class': 'form-input',
                'placeholder': 'Ex: RSSI -85 dBm, RSRP -100 dBm',
            }),
            'modele_telephone': forms.TextInput(attrs={
                'class': 'form-input',
                'placeholder': 'Ex: Samsung A14, iPhone 12...',
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['forfait_prix'].required = False
        self.fields['commentaire'].required = False
        self.fields['puissance_signal'].required = False
        self.fields['modele_telephone'].required = False

    def clean_quartier(self):
        quartier = self.cleaned_data.get('quartier', '')
        quartier = quartier.strip().title()
        if len(quartier) < 3:
            raise forms.ValidationError(
                "Le nom du quartier doit contenir au moins 3 caracteres."
            )
        caracteres_interdits = ['<', '>', 'script', 'javascript', 'onclick', 'http']
        for char in caracteres_interdits:
            if char.lower() in quartier.lower():
                raise forms.ValidationError("Caracteres non autorises detectes.")
        return quartier