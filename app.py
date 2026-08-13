"""
Plataforma de busca de editais do PNCP.

Backend Flask que faz a intermediação com a API pública do PNCP
(pncp.gov.br/api). Resolve o CORS do navegador e monta a tabela
item a item (busca o edital + os itens de cada edital).

Rodar local:   python app.py
Produção:      gunicorn app:app
"""

import concurrent.futures
import csv
import io

import requests
from flask import Flask, Response, jsonify, request, send_from_directory

app = Flask(__name__, static_folder="static", static_url_path="")

SEARCH_URL = "https://pncp.gov.br/api/search/"
ITENS_URL = "https://pncp.gov.br/api/pncp/v1/orgaos/{cnpj}/compras/{ano}/{seq}/itens"

# A API do PNCP recusa User-Agents não-navegador (fecha a conexão),
# então usamos um cabeçalho de navegador real.
HEADERS = {
    "Accept": "application/json",
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    ),
}

# Quantos editais por página buscamos da API de search.
TAM_PAGINA = 10
# Quantas requisições de itens disparamos em paralelo.
MAX_WORKERS = 8
TIMEOUT = 30


def fetch_search(params):
    """Consulta a API de busca do PNCP (nível edital)."""
    query = {
        "q": params.get("q", ""),
        "tipos_documento": "edital",
        "ordenacao": "-data",
        "pagina": params.get("pagina", "1"),
        "tam_pagina": TAM_PAGINA,
        "status": params.get("status", "recebendo_proposta"),
    }
    # UF e esfera só entram na query se preenchidos (vazio = todos).
    if params.get("uf"):
        query["ufs"] = params["uf"]
    if params.get("esfera"):
        query["esferas"] = params["esfera"]

    resp = requests.get(SEARCH_URL, params=query, headers=HEADERS, timeout=TIMEOUT)
    resp.raise_for_status()
    return resp.json()


def parse_item_url(item_url):
    """'/compras/{cnpj}/{ano}/{seq}' -> (cnpj, ano, seq)."""
    parts = [p for p in (item_url or "").split("/") if p]
    # parts == ['compras', cnpj, ano, seq]
    if len(parts) >= 4 and parts[0] == "compras":
        return parts[1], parts[2], parts[3]
    return None


def fetch_itens(edital):
    """Busca os itens de um edital e devolve uma linha por item."""
    ref = parse_item_url(edital.get("item_url"))
    # Formato igual ao portal: "Cidade/UF".
    local = "/".join(
        p for p in [edital.get("municipio_nome"), edital.get("uf")] if p
    )
    # A pagina do edital no portal usa /app/editais/{cnpj}/{ano}/{seq}
    # (sem o "/compras" que vem no item_url da API).
    if ref:
        link = "https://pncp.gov.br/app/editais/{}/{}/{}".format(*ref)
    else:
        link = "https://pncp.gov.br/app/editais"
    base = {
        "local": local,
        "orgao": edital.get("orgao_nome"),
        "data_fim": edital.get("data_fim_vigencia"),
        "edital": edital.get("title"),
        "esfera": edital.get("esfera_nome"),
        "link": link,
    }
    if not ref:
        return [{**base, "item": None, "descricao": edital.get("description"),
                 "quantidade": None, "valor_unitario": None, "valor_total": None}]

    cnpj, ano, seq = ref
    url = ITENS_URL.format(cnpj=cnpj, ano=ano, seq=seq)
    try:
        resp = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
        resp.raise_for_status()
        itens = resp.json()
    except Exception:
        itens = []

    if not itens:
        return [{**base, "item": None, "descricao": edital.get("description"),
                 "quantidade": None, "valor_unitario": None, "valor_total": None}]

    rows = []
    for it in itens:
        rows.append({
            **base,
            "item": it.get("numeroItem"),
            "descricao": it.get("descricao"),
            "quantidade": it.get("quantidade"),
            "unidade": it.get("unidadeMedida"),
            "valor_unitario": it.get("valorUnitarioEstimado"),
            "valor_total": it.get("valorTotal"),
        })
    return rows


def build_rows(params):
    """Busca os editais e expande em linhas por item (em paralelo).
    Depois filtra apenas os itens que contêm a palavra-chave digitada.
    """
    data = fetch_search(params)
    editais = data.get("items", [])
    total = data.get("total") or len(editais)

    rows = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
        for result in pool.map(fetch_itens, editais):
            rows.extend(result)

    # --- NOVO: filtrar apenas itens que contenham a palavra-chave ---
    q = (params.get("q") or "").strip().lower()
    if q:
        rows_filtradas = []
        for r in rows:
            descricao = (r.get("descricao") or "").lower()
            edital_titulo = (r.get("edital") or "").lower()
            # mantém a linha se a palavra-chave aparecer na descrição do item
            # ou no título do edital
            if q in descricao or q in edital_titulo:
                rows_filtradas.append(r)
        rows = rows_filtradas
    # ---------------------------------------------------------------

    return rows, total


@app.route("/")
def index():
    return send_from_directory(app.static_folder, "index.html")


@app.route("/api/buscar")
def buscar():
    params = {
        "q": request.args.get("q", ""),
        "uf": request.args.get("uf", ""),
        "esfera": request.args.get("esfera", ""),
        "status": request.args.get("status", "recebendo_proposta"),
        "pagina": request.args.get("pagina", "1"),
    }
    try:
        rows, total = build_rows(params)
    except requests.HTTPError as exc:
        return jsonify({"erro": f"Erro na API do PNCP: {exc}"}), 502
    except Exception as exc:  # noqa: BLE001
        return jsonify({"erro": str(exc)}), 500

    return jsonify({
        "linhas": rows,
        "total_editais": total,
        "pagina": int(params["pagina"]),
        "tam_pagina": TAM_PAGINA,
    })


@app.route("/api/exportar")
def exportar():
    """Mesma busca, devolvida como CSV (planilha)."""
    params = {
        "q": request.args.get("q", ""),
        "uf": request.args.get("uf", ""),
        "esfera": request.args.get("esfera", ""),
        "status": request.args.get("status", "recebendo_proposta"),
        "pagina": request.args.get("pagina", "1"),
    }
    rows, _ = build_rows(params)

    cols = [
        ("local", "Local"),
        ("orgao", "Órgão"),
        ("data_fim", "Data fim recebimento"),
        ("item", "Item"),
        ("descricao", "Descrição"),
        ("quantidade", "Quantidade"),
        ("valor_unitario", "Valor unitário estimado"),
        ("valor_total", "Valor total estimado"),
    ]
    buf = io.StringIO()
    writer = csv.writer(buf, delimiter=";")
    writer.writerow([label for _, label in cols])
    for r in rows:
        writer.writerow([r.get(key, "") for key, _ in cols])

    # BOM para o Excel abrir acentos corretamente.
    csv_bytes = ("﻿" + buf.getvalue()).encode("utf-8")
    return Response(
        csv_bytes,
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment; filename=editais_pncp.csv"},
    )


if __name__ == "__main__":
    # use_reloader=False evita falha do auto-reload no Windows; produção usa gunicorn.
    app.run(host="0.0.0.0", port=5000, debug=True, use_reloader=False)
