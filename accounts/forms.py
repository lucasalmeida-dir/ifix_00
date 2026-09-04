from django import forms
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm
from django.contrib.auth.models import User

from .models import Profile


class IFIXAuthenticationForm(AuthenticationForm):
    def clean(self):
        try:
            return super().clean()
        except forms.ValidationError:
            raise forms.ValidationError('Errou a senha')


class UserRegisterForm(UserCreationForm):
    """Cadastro de usuário (U1 - Cadastro de usuário)."""

    first_name = forms.CharField(required=True, label='Nome')
    last_name = forms.CharField(required=True, label='Sobrenome')
    email = forms.EmailField(required=True, label='E-mail')
    telefone = forms.CharField(required=True, label='Telefone')
    endereco = forms.CharField(required=True, label='Endereço')
    numero = forms.CharField(required=True, label='Número', widget=forms.TextInput(attrs={'style': 'max-width: 180px;'}))
    complemento = forms.CharField(required=True, label='Complemento', widget=forms.TextInput(attrs={'style': 'max-width: 280px;'}))
    foto = forms.FileField(required=True, label='Foto de perfil', widget=forms.ClearableFileInput(attrs={'accept': 'image/*'}))

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
            numero=self.cleaned_data.get('numero', ''),
            complemento=self.cleaned_data.get('complemento', ''),
            foto=self.cleaned_data.get('foto'),
        )
        return user

    def clean_password2(self):
        try:
            return super().clean_password2()
        except forms.ValidationError:
            raise forms.ValidationError('Errou a senha')


class ProfessionalRegisterForm(UserCreationForm):
    """Cadastro profissional (P1 - Cadastro profissional)."""

    first_name = forms.CharField(required=True, label='Nome')
    last_name = forms.CharField(required=True, label='Sobrenome')
    email = forms.EmailField(required=True, label='E-mail')
    telefone = forms.CharField(required=True, label='Telefone')
    endereco = forms.CharField(required=True, label='Endereço')
    numero = forms.CharField(required=True, label='Número', widget=forms.TextInput(attrs={'style': 'max-width: 180px;'}))
    complemento = forms.CharField(required=True, label='Complemento', widget=forms.TextInput(attrs={'style': 'max-width: 280px;'}))
    foto = forms.FileField(required=True, label='Foto de perfil', widget=forms.ClearableFileInput(attrs={'accept': 'image/*'}))
    especialidade = forms.CharField(
        required=True, label='Especialidade/Área de atuação',
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
            numero=self.cleaned_data.get('numero', ''),
            complemento=self.cleaned_data.get('complemento', ''),
            foto=self.cleaned_data.get('foto'),
            especialidade=self.cleaned_data.get('especialidade', ''),
        )
        return user

    def clean_password2(self):
        try:
            return super().clean_password2()
        except forms.ValidationError:
            raise forms.ValidationError('Errou a senha')


class ProfileEditForm(forms.ModelForm):
    """Editar perfil (U2 - Editar perfil / P2 - Editar dados profissionais)."""

    first_name = forms.CharField(required=False, label='Nome')
    last_name = forms.CharField(required=False, label='Sobrenome')
    email = forms.EmailField(required=False, label='E-mail')
    foto = forms.FileField(
        required=False,
        label='Foto de perfil',
        widget=forms.FileInput(attrs={'accept': 'image/*', 'class': 'profile-photo-input'}),
    )

    class Meta:
        model = Profile
        fields = ['telefone', 'endereco', 'numero', 'complemento', 'foto', 'especialidade']
        labels = {
            'telefone': 'Telefone',
            'endereco': 'Endereço',
            'numero': 'Número',
            'complemento': 'Complemento',
            'foto': 'Foto de perfil',
            'especialidade': 'Especialidade/Área de atuação',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['numero'].widget.attrs['style'] = 'max-width: 180px;'
        self.fields['complemento'].widget.attrs['style'] = 'max-width: 280px;'
        if self.instance and self.instance.user_id:
            self.fields['first_name'].initial = self.instance.user.first_name
            self.fields['last_name'].initial = self.instance.user.last_name
            self.fields['email'].initial = self.instance.user.email
        if not (self.instance and self.instance.is_profissional):
            # Usuários comuns não têm especialidade profissional.
            del self.fields['especialidade']
        field_order = [
            'foto',
            'first_name',
            'last_name',
            'especialidade',
            'email',
            'telefone',
            'endereco',
            'numero',
            'complemento',
        ]
        self.order_fields([field_name for field_name in field_order if field_name in self.fields])

    def save(self, commit=True):
        profile = super().save(commit=commit)
        if self.cleaned_data.get('foto'):
            profile.foto = self.cleaned_data['foto']
            if commit:
                profile.save(update_fields=['foto'])
        user = profile.user
        user.first_name = self.cleaned_data.get('first_name', '')
        user.last_name = self.cleaned_data.get('last_name', '')
        user.email = self.cleaned_data.get('email', '')
        if commit:
            user.save()
        return profile
