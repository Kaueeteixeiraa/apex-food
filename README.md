# Apex Food

MVP SaaS em Flask para restaurantes, lanchonetes, pizzarias, cafeterias, bares e fast foods. O projeto usa SQLite inicialmente, templates HTML organizados, CSS/JS separados e uma interface escura moderna.

## Funcionalidades do MVP

- Cadastro de empresa e administrador.
- Login com sessão.
- Dashboard com vendas do dia, pedidos, ticket médio, mesas ocupadas, pedidos em preparo, alertas e gráfico simples.
- Pedidos com criação, listagem, filtro por status e mudança de status.
- Caixa / PDV com abertura, fechamento e finalização de venda.
- Visão do Salão com áreas, mesas redondas/quadradas/retangulares, drag, resize, status e salvamento no banco.
- Cardápio / produtos com cadastro e disponibilidade.
- Clientes com histórico básico.
- Estoque simples com alerta de mínimo.
- Funcionários com permissões.
- Cozinha / KDS simples para pedidos ativos.

## Stack

- Python
- Flask
- SQLite
- HTML, CSS e JavaScript sem build step

## Como rodar

```bash
cd Apex-Food
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python run.py
```

Acesse:

```text
http://127.0.0.1:5000
```

Credenciais demo criadas automaticamente:

```text
E-mail: admin@apexfood.local
Senha: 123456
```

O banco SQLite fica em:

```text
instance/apex_food.sqlite
```

Para recriar os dados demo, apague o arquivo do banco e rode o app novamente.

## Estrutura

```text
Apex-Food/
  app/
    routes/          Rotas separadas por módulo
    static/css/      Estilos do sistema
    static/js/       Interações do dashboard, PDV e salão
    templates/       Telas HTML organizadas
    database.py      Conexão, inicialização e seed SQLite
    schema.sql       Tabelas do MVP
    models.py        Listas de status, segmentos e permissões
  run.py             Entrada local
  requirements.txt
```

## Preparado para evoluir

O schema foi mantido relacional e simples para facilitar migração futura para PostgreSQL/Supabase. Próximos passos naturais:

- Trocar `sqlite3` por SQLAlchemy ou SQLModel.
- Criar migrations com Alembic.
- Adicionar multiusuário com permissões por rota.
- Evoluir pedidos para múltiplos itens editáveis em tempo real.
- Adicionar upload real de imagem de produto.
- Criar integrações futuras com delivery, fiscal e pagamentos.
