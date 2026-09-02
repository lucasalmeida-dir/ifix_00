from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User

from .models import Profile


class UserRegisterForm(UserCreationForm):
    """Cadastro de usuário (U1 - Cadastro de usuário)."""

    email = forms.EmailField(required=True, label='E-mail')
    telefone = forms.CharField(required=False, label='Telefone')
    endereco = forms.CharField(required=False, label='Endereço')

    class Meta:
        model = User
        fields = ['username', 'first_name', 'last_name', 'email', 'password1', 'password2']
        labels = {
            'username': 'Usuário',
            'first_name': 'Nome',
            'last_name': 'Sobrenome',
        }

    def save(self, commit=True):
        user = super().save(commit=commit)
        Profile.objects.create(
            user=user,
            tipo=Profile.TIPO_USUARIO,
            telefone=self.cleaned_data.get('telefone', ''),
            endereco=self.cleaned_data.get('endereco', ''),
        )
        return user


class ProfessionalRegisterForm(UserCreationForm):
    """Cadastro profissional (P1 - Cadastro profissional)."""

    email = forms.EmailField(required=True, label='E-mail')
    telefone = forms.CharField(required=False, label='Telefone')
    endereco = forms.CharField(required=False, label='Endereço')
    especialidade = forms.CharField(
        required=False, label='Especialidade/Área de atuação',
        help_text='Ex: Hidráulica, Elétrica, Marcenaria...'
    )

    class Meta:
        model = User
        fields = ['username', 'first_name', 'last_name', 'email', 'password1', 'password2']
        labels = {
            'username': 'Usuário',
            'first_name': 'Nome',
            'last_name': 'Sobrenome',
        }

    def save(self, commit=True):
        user = super().save(commit=commit)
        Profile.objects.create(
            user=user,
            tipo=Profile.TIPO_PROFISSIONAL,
            telefone=self.cleaned_data.get('telefone', ''),
            endereco=self.cleaned_data.get('endereco', ''),
            especialidade=self.cleaned_data.get('especialidade', ''),
        )
        return user


class ProfileEditForm(forms.ModelForm):
    """Editar perfil (U2 - Editar perfil / P2 - Editar dados profissionais)."""

    first_name = forms.CharField(required=False, label='Nome')
    last_name = forms.CharField(required=False, label='Sobrenome')
    email = forms.EmailField(required=False, label='E-mail')

    class Meta:
        model = Profile
        fields = ['telefone', 'endereco', 'especialidade']
        labels = {
            'telefone': 'Telefone',
            'endereco': 'Endereço',
            'especialidade': 'Especialidade/Área de atuação',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.user_id:
            self.fields['first_name'].initial = self.instance.user.first_name
            self.fields['last_name'].initial = self.instance.user.last_name
            self.fields['email'].initial = self.instance.user.email
        if not (self.instance and self.instance.is_profissional):
            # Usuários comuns não têm especialidade profissional.
            del self.fields['especialidade']

    def save(self, commit=True):
        profile = super().save(commit=commit)
        user = profile.user
        user.first_name = self.cleaned_data.get('first_name', '')
        user.last_name = self.cleaned_data.get('last_name', '')
        user.email = self.cleaned_data.get('email', '')
        if commit:
            user.save()
        return profile
