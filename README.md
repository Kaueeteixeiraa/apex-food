# Apex Food

MVP SaaS em Flask para restaurantes, lanchonetes, pizzarias, cafeterias, bares e fast foods. O projeto usa SQLite inicialmente, templates HTML organizados, CSS/JS separados e uma interface escura moderna com foco em operacao real.

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

Credenciais demo:

```text
E-mail: admin@apexfood.local
Senha: 123456
```

O banco SQLite fica em:

```text
instance/apex_food.sqlite
```

Para recriar os dados demo, apague o arquivo do banco e rode o app novamente.

## Telas disponiveis

- Login com transicao de carregamento.
- Cadastro de empresa em formato de onboarding por etapas.
- Dashboard principal com metricas, alertas, grafico e pedidos recentes.
- Pedidos com criacao, listagem, filtro por status e troca de status.
- Caixa / PDV com abertura, fechamento e finalizacao de venda.
- Visao do Salao com areas, mesas arrastaveis, resize, status e painel lateral.
- Cardapio / produtos com cadastro, categorias e disponibilidade.
- Clientes com historico basico.
- Estoque simples com alerta de minimo.
- Funcionarios com permissao por perfil.
- Cozinha / KDS simples para pedidos ativos.

## Melhorias visuais recentes

- Tema escuro redesenhado com grafite, roxo neon, laranja food, verde positivo, azul informativo e vermelho para alerta.
- Botoes refeitos com variantes principal, positiva, alerta, perigosa e neutra.
- Selects/dropdowns com fundo escuro, texto claro e setas customizadas.
- Login redesenhado com card mais forte, inputs com icones, fundo em grid/gradiente e overlay "Entrando no Apex Food...".
- Cadastro transformado em onboarding com progresso por etapas: empresa, endereco, administrador e finalizacao.
- Dashboard compactado para caber melhor no viewport, com cards menores e grafico escuro mais coerente.
- Tabelas, cards, badges e status ganharam contraste, hover e animacoes suaves.
- Telas principais usam altura controlada e scroll interno quando necessario, evitando rolagem vertical da pagina.
- Visao do Salao recebeu grid mais limpo, status mais visiveis, legenda compacta e painel lateral animado.

## Funcionalidades do MVP

- Cadastro de empresa e administrador.
- Login com sessao.
- Dashboard com vendas do dia, pedidos, ticket medio, mesas ocupadas, pedidos em preparo, alertas e grafico simples.
- Pedidos com criacao, listagem, filtro por status e mudanca de status.
- Caixa / PDV com abertura, fechamento e finalizacao de venda.
- Visao do Salao com areas, mesas redondas/quadradas/retangulares, drag, resize, status e salvamento no banco.
- Cardapio / produtos com cadastro e disponibilidade.
- Clientes com historico basico.
- Estoque simples com alerta de minimo.
- Funcionarios com permissoes.
- Cozinha / KDS simples para pedidos ativos.

## Stack

- Python
- Flask
- SQLite
- HTML, CSS e JavaScript sem build step

## Estrutura

```text
Apex-Food/
  app/
    routes/          Rotas separadas por modulo
    static/css/      Estilos do sistema
    static/js/       Interacoes do dashboard, PDV, onboarding e salao
    templates/       Telas HTML organizadas
    database.py      Conexao, inicializacao e seed SQLite
    schema.sql       Tabelas do MVP
    models.py        Listas de status, segmentos e permissoes
  run.py             Entrada local
  requirements.txt
```

## Preparado para evoluir

O schema foi mantido relacional e simples para facilitar migracao futura para PostgreSQL/Supabase. Proximos passos naturais:

- Trocar `sqlite3` por SQLAlchemy ou SQLModel.
- Criar migrations com Alembic.
- Adicionar multiusuario com permissoes por rota.
- Evoluir pedidos para multiplos itens editaveis em tempo real.
- Adicionar upload real de imagem de produto.
- Criar integracoes futuras com delivery, fiscal e pagamentos.
