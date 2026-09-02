# Homeservices — Django

Projeto Django gerado a partir do diagrama de fluxo (Mermaid) com três grandes áreas:

- **Autenticação**: login, logout e recuperação de senha.
- **Área do Usuário**: cadastro, editar perfil, visualizar serviços, buscar
  profissionais, filtrar por categoria, consultar preço/duração e solicitar serviço.
- **Área do Profissional**: cadastro profissional, editar dados profissionais,
  categorias de serviço (Hidráulica, Elétrica, Desentupimento, Marcenaria, Seu
  problema) e cadastro de serviços (nome, descrição, preço, duração, salvar —
  ficando disponível para os usuários).

## Estrutura

```
homeservices/
├── manage.py
├── requirements.txt
├── core_views.py          # view da página inicial (home)
├── homeservices/           # configurações do projeto (settings, urls)
├── accounts/                # Autenticação + cadastro/edição de perfil
│   ├── models.py            # Profile (tipo: usuário/profissional)
│   ├── forms.py
│   ├── views.py
│   ├── urls.py
│   ├── decorators.py        # @user_required / @professional_required
│   └── templates/accounts/
├── services/                 # Serviços, categorias e solicitações
│   ├── models.py             # CategoriaServico, Servico, SolicitacaoServico
│   ├── forms.py
│   ├── views.py
│   ├── urls.py
│   └── templates/services/
├── templates/                # base.html, home.html
└── static/css/style.css
```

## Como executar

```bash
# 1. Crie um ambiente virtual (opcional, mas recomendado)
python3 -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate

# 2. Instale as dependências
pip install -r requirements.txt

# 3. Aplique as migrations (isso já cria as 5 categorias de serviço)
python manage.py migrate

# 4. Crie um super usuário para acessar o /admin
python manage.py createsuperuser

# 5. Rode o servidor de desenvolvimento
python manage.py runserver
```

Acesse http://127.0.0.1:8000/

## Fluxo de uso

1. Na home, escolha **"Criar conta de usuário"** ou **"Criar conta profissional"**.
2. **Profissional**: após logar, vá em *Meus serviços → Adicionar serviço* e
   preencha categoria, nome, descrição, preço e duração. Ao salvar, o serviço
   fica disponível para os usuários (equivalente ao nó "Serviço disponível
   para usuários" do diagrama).
3. **Usuário**: em *Ver serviços*, é possível buscar por nome do profissional/serviço
   e filtrar por categoria. Ao abrir um serviço, os dados de preço e duração
   aparecem, com o botão para *Solicitar este serviço*.
4. O profissional acompanha os pedidos recebidos em *Solicitações recebidas*,
   e o usuário acompanha os seus em *Minhas solicitações*.
5. Recuperação de senha: em `/conta/senha/recuperar/` — como o projeto usa o
   backend de e-mail "console" por padrão, o link de redefinição aparece no
   terminal onde o `runserver` está rodando.

## Painel administrativo

Em `/admin/` (usando o super usuário criado), é possível gerenciar usuários,
perfis, categorias, serviços e solicitações diretamente.

## Próximos passos (integração de front-end)

Este projeto foi estruturado para facilitar a substituição do front-end:
- Os templates estendem `templates/base.html`, então a identidade visual pode
  ser trocada em um único lugar (nav, cores, fontes, etc).
- As views retornam contexto simples (`servicos`, `form`, `categorias`,
  `solicitacoes`, etc.), então templates novos podem ser plugados sem alterar
  `views.py`.
- `static/css/style.css` contém apenas estilos mínimos — pode ser substituído
  por um design system próprio (ex.: inspirado em outro site de referência).
