# Busca de Editais — PNCP

Plataforma web simples para buscar e extrair editais do portal
[PNCP](https://pncp.gov.br/app/editais). Consulta a **API pública oficial**
do PNCP (sem scraping), aplica os filtros e mostra os dados item a item
numa tabela, com exportação para planilha (CSV).

## Como funciona

1. O frontend envia os filtros (palavra-chave, UF, esfera, status) ao backend.
2. O backend consulta a API de busca do PNCP (`/api/search`) — nível edital.
3. Para cada edital, busca os itens (`/v1/orgaos/.../itens`) — nível item.
4. Junta tudo numa tabela com as colunas:
   `local · órgão · data fim · item · descrição · quantidade · valor unitário · valor total`.

> Não usa banco de dados — os dados vêm direto da fonte, sempre atualizados.

## Rodar localmente

Requer Python 3.10+.

```bash
pip install -r requirements.txt
python app.py
```

Acesse: http://localhost:5000

## Publicar de graça (Render)

1. Suba esta pasta para um repositório no GitHub.
2. Em [render.com](https://render.com) → **New + → Web Service** → conecte o repo.
3. O `render.yaml` já configura tudo (plano Free).
   - Build: `pip install -r requirements.txt`
   - Start: `gunicorn app:app`
4. Em ~2 min você recebe uma URL pública pronta para usar.

> No plano free o serviço "dorme" após inatividade; a primeira busca após
> um tempo parado leva alguns segundos a mais para acordar. Depois fica rápido.

## Estrutura

```
app.py            backend Flask (proxy + montagem da tabela)
static/index.html interface (filtros, tabela, paginação, exportar)
requirements.txt  dependências
render.yaml       deploy automático no Render (free)
Procfile          start command (Render / Railway / Heroku)
```
