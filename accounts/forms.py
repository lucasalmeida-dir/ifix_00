from django import forms
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm
from django.contrib.auth.models import User

from .models import Profile
from .services import CepInvalidoError, consultar_cep, somente_digitos as _somente_digitos

# Opções fixas de especialidade/área de atuação, usadas tanto no cadastro
# profissional quanto na edição de dados profissionais — mantidas num só
# lugar para as duas telas nunca ficarem dessincronizadas.
ESPECIALIDADE_CHOICES = (
    ('', 'Selecione uma especialidade'),
    ('Elétrica', 'Elétrica'),
    ('Hidráulica', 'Hidráulica'),
    ('Marcenaria', 'Marcenaria'),
    ('Pintura', 'Pintura'),
)


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
    cep = forms.CharField(
        required=True, label='CEP', max_length=9,
        widget=forms.TextInput(attrs={
            'placeholder': '00000-000', 'maxlength': '9', 'class': 'cep-input',
        }),
        help_text='Usado internamente para calcular a distância até os profissionais.',
    )
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

    def clean_cep(self):
        cep = self.cleaned_data.get('cep', '')
        try:
            info_cep = consultar_cep(cep)
        except CepInvalidoError as exc:
            raise forms.ValidationError(str(exc))
        self.cleaned_data['cep_info'] = info_cep
        return info_cep['cep']

    def save(self, commit=True):
        user = super().save(commit=commit)
        cep_info = self.cleaned_data.get('cep_info') or {}
        Profile.objects.create(
            user=user,
            tipo=Profile.TIPO_USUARIO,
            telefone=self.cleaned_data.get('telefone', ''),
            cep=self.cleaned_data.get('cep', ''),
            latitude=cep_info.get('latitude'),
            longitude=cep_info.get('longitude'),
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
    cep = forms.CharField(
        required=True, label='CEP', max_length=9,
        widget=forms.TextInput(attrs={
            'placeholder': '00000-000', 'maxlength': '9', 'class': 'cep-input',
        }),
        help_text='Usado internamente para calcular a distância até os clientes.',
    )
    endereco = forms.CharField(required=True, label='Endereço')
    numero = forms.CharField(required=True, label='Número', widget=forms.TextInput(attrs={'style': 'max-width: 180px;'}))
    complemento = forms.CharField(required=True, label='Complemento', widget=forms.TextInput(attrs={'style': 'max-width: 280px;'}))
    foto = forms.FileField(required=True, label='Foto de perfil', widget=forms.ClearableFileInput(attrs={'accept': 'image/*'}))
    especialidade = forms.ChoiceField(
        required=True, label='Especialidade/Área de atuação',
        choices=ESPECIALIDADE_CHOICES,
    )

    class Meta:
        model = User
        fields = ['username', 'first_name', 'last_name', 'email', 'password1', 'password2']
        labels = {
            'username': 'Usuário',
            'first_name': 'Nome',
            'last_name': 'Sobrenome',
        }

    def clean_cep(self):
        cep = self.cleaned_data.get('cep', '')
        try:
            info_cep = consultar_cep(cep)
        except CepInvalidoError as exc:
            raise forms.ValidationError(str(exc))
        self.cleaned_data['cep_info'] = info_cep
        return info_cep['cep']

    def save(self, commit=True):
        user = super().save(commit=commit)
        cep_info = self.cleaned_data.get('cep_info') or {}
        Profile.objects.create(
            user=user,
            tipo=Profile.TIPO_PROFISSIONAL,
            telefone=self.cleaned_data.get('telefone', ''),
            cep=self.cleaned_data.get('cep', ''),
            latitude=cep_info.get('latitude'),
            longitude=cep_info.get('longitude'),
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
    especialidade = forms.ChoiceField(
        required=True, label='Especialidade/Área de atuação',
        choices=ESPECIALIDADE_CHOICES,
    )

    cep = forms.CharField(
        required=True, label='CEP', max_length=9,
        widget=forms.TextInput(attrs={
            'placeholder': '00000-000', 'maxlength': '9', 'class': 'cep-input',
        }),
        help_text='Usado internamente para calcular a distância até profissionais/clientes.',
    )

    class Meta:
        model = Profile
        fields = ['telefone', 'cep', 'endereco', 'numero', 'complemento', 'foto', 'especialidade']
        labels = {
            'telefone': 'Telefone',
            'cep': 'CEP',
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
            'cep',
            'endereco',
            'numero',
            'complemento',
        ]
        self.order_fields([field_name for field_name in field_order if field_name in self.fields])

    def clean_cep(self):
        cep = self.cleaned_data.get('cep', '')
        cep_atual = self.instance.cep if self.instance else ''
        ja_tem_localizacao = bool(self.instance and self.instance.tem_localizacao)
        cep_mudou = _somente_digitos(cep) != _somente_digitos(cep_atual)
        # Só pula a consulta se o CEP não mudou E o perfil já tem coordenadas
        # (evita reconsultar à toa, mas corrige sozinho perfis antigos sem lat/long).
        if not cep_mudou and cep_atual and ja_tem_localizacao:
            return cep_atual
        try:
            info_cep = consultar_cep(cep)
        except CepInvalidoError as exc:
            raise forms.ValidationError(str(exc))
        self.cleaned_data['cep_info'] = info_cep
        return info_cep['cep']

    def save(self, commit=True):
        profile = super().save(commit=False)
        if self.cleaned_data.get('foto'):
            profile.foto = self.cleaned_data['foto']
        cep_info = self.cleaned_data.get('cep_info')
        if cep_info:
            profile.latitude = cep_info.get('latitude')
            profile.longitude = cep_info.get('longitude')
        user = profile.user
        user.first_name = self.cleaned_data.get('first_name', '')
        user.last_name = self.cleaned_data.get('last_name', '')
        user.email = self.cleaned_data.get('email', '')
        if commit:
            profile.save()
            user.save()
        return profile
