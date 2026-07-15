# Apex Food

SaaS Flask para operacao de restaurantes, lanchonetes, pizzarias, cafeterias, bares e delivery.

## Rodar localmente

```bash
cd Apex-Food
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python run.py
```

Acesse `http://127.0.0.1:5000`.

## Acessos

Clientes nao se cadastram publicamente. Empresas, usuarios responsaveis, planos, licencas e convites sao criados no Apex Admin.

Para criar o primeiro admin global em ambiente novo, defina:

```bash
set APEX_PLATFORM_ADMIN_EMAIL=admin@suaempresa.com
set APEX_PLATFORM_ADMIN_PASSWORD=uma-senha-segura
```

Login cliente: `/auth/login`  
Login Apex Admin: `/apex-admin/login`

## Demo

Dados demo nao sao criados automaticamente. Para ambiente local demonstrativo:

```bash
set APEX_FOOD_SEED_DEMO=1
python run.py
```

## Estrutura

- `app/routes/apex_admin.py`: administracao global.
- `app/routes/auth.py`: login cliente, convite e recuperacao.
- `app/services/saas.py`: licencas, convites, auditoria e configuracoes.
- `app/templates/apex_admin/`: telas do Apex Admin.
- `app/static/css/saas.css`: identidade compartilhada de auth/admin.
- `tests/test_saas_access.py`: testes de acesso, cadastro admin, convite e licenca.

## Banco

SQLite em desenvolvimento. Migrations Alembic em `migrations/versions`.
