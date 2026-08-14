import os
import json
import csv
import io
import base64
import concurrent.futures
import requests
from datetime import datetime
from pathlib import Path
import resend

# ================== CONFIGURAÇÕES ==================
PALAVRAS_CHAVE = [
    "starlink",
    "internet satélite",
    "antena starlink",
    "kit starlink",
    "orbita baixa",
    "café gourmet",
    "rádio transceptor",
    "rádio comunicador",
    "termohigrometro",
    "termo higrometro",
    "impressora termica",
    "adaptador wireless",
    "wirelss usb",
    "kit de robótica",
    "robótica",
    "mesa de som",
    "tripe retratil",
    "suporte articulado",
    "pilha",
]

STATUS = "recebendo_proposta"
SEEN_FILE = Path("seen_items.json")
MAX_SEEN = 5000
# ==================================================

resend.api_key = os.environ.get("RESEND_API_KEY")
EMAIL_DESTINO = os.environ.get("EMAIL_DESTINO")

SEARCH_URL = "https://pncp.gov.br/api/search/"
ITENS_URL = "https://pncp.gov.br/api/pncp/v1/orgaos/{cnpj}/compras/{ano}/{seq}/itens"

HEADERS = {
    "Accept": "application/json",
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    ),
}

TAM_PAGINA = 10
MAX_WORKERS = 6
TIMEOUT = 30


def carregar_vistos():
    if SEEN_FILE.exists():
        try:
            with open(SEEN_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                return set(data.get("ids", []))
        except Exception:
            return set()
    return set()


def salvar_vistos(ids):
    lista = list(ids)[-MAX_SEEN:]
    with open(SEEN_FILE, "w", encoding="utf-8") as f:
        json.dump(
            {"ids": lista, "atualizado_em": datetime.now().isoformat()},
            f,
            ensure_ascii=False,
            indent=2,
        )


def id_unico(r):
    link = r.get("link") or ""
    item = r.get("item")
    return f"{link}|{item}"


def fetch_search(q):
    query = {
        "q": q,
        "tipos_documento": "edital",
        "ordenacao": "-data",
        "pagina": "1",
        "tam_pagina": TAM_PAGINA,
        "status": STATUS,
    }
    resp = requests.get(SEARCH_URL, params=query, headers=HEADERS, timeout=TIMEOUT)
    resp.raise_for_status()
    return resp.json()


def parse_item_url(item_url):
    parts = [p for p in (item_url or "").split("/") if p]
    if len(parts) >= 4 and parts[0] == "compras":
        return parts[1], parts[2], parts[3]
    return None


def fetch_itens(edital, palavra):
    ref = parse_item_url(edital.get("item_url"))
    cidade = edital.get("municipio_nome") or ""
    estado = edital.get("uf") or ""

    if ref:
        link = f"https://pncp.gov.br/app/editais/{ref[0]}/{ref[1]}/{ref[2]}"
    else:
        link = "https://pncp.gov.br/app/editais"

    base = {
        "orgao": edital.get("orgao_nome"),
        "cidade": cidade,
        "estado": estado,
        "data_fim": edital.get("data_fim_vigencia"),
        "edital": edital.get("title"),
        "link": link,
        "palavra": palavra,
    }

    if not ref:
        return []

    cnpj, ano, seq = ref
    url = ITENS_URL.format(cnpj=cnpj, ano=ano, seq=seq)
    try:
        resp = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
        resp.raise_for_status()
        itens = resp.json()
    except Exception:
        return []

    rows = []
    palavra_lower = palavra.lower()
    for it in itens:
        descricao = (it.get("descricao") or "").lower()
        if palavra_lower in descricao:
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


def formatar_data(valor):
    if not valor:
        return ""
    try:
        if "T" in str(valor):
            dt = datetime.fromisoformat(str(valor).replace("Z", ""))
        else:
            dt = datetime.strptime(str(valor)[:10], "%Y-%m-%d")
        return dt.strftime("%d/%m/%Y")
    except Exception:
        return str(valor)


def buscar_todas():
    todos_resultados = []
    for palavra in PALAVRAS_CHAVE:
        print(f"Buscando: {palavra}")
        try:
            data = fetch_search(palavra)
            editais = data.get("items", [])
            with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
                futures = [pool.submit(fetch_itens, ed, palavra) for ed in editais]
                for f in concurrent.futures.as_completed(futures):
                    todos_resultados.extend(f.result())
        except Exception as e:
            print(f"Erro na palavra '{palavra}': {e}")
    return todos_resultados


def montar_html(resultados):
    if not resultados:
        return None

    html = f"""
    <h2>Novas oportunidades no PNCP</h2>
    <p>Foram encontrados <strong>{len(resultados)}</strong> item(ns) <u>novos</u>:</p>
    <hr>
    """

    for r in resultados:
        html += f"""
        <div style="margin-bottom: 20px; padding: 12px; border: 1px solid #ddd; border-radius: 8px;">
            <p><strong>Palavra-chave:</strong> {r['palavra']}</p>
            <p><strong>Órgão:</strong> {r.get('orgao') or '—'}</p>
            <p><strong>Cidade/UF:</strong> {r.get('cidade') or '—'} / {r.get('estado') or '—'}</p>
            <p><strong>Data fim:</strong> {formatar_data(r.get('data_fim'))}</p>
            <p><strong>Item:</strong> {r.get('item') or '—'}</p>
            <p><strong>Descrição:</strong> {r.get('descricao') or '—'}</p>
            <p><strong>Quantidade:</strong> {r.get('quantidade') or '—'} {r.get('unidade') or ''}</p>
            <p><a href="{r.get('link')}" target="_blank">Ver edital completo</a></p>
        </div>
        """
    return html


def gerar_csv(resultados):
    """Gera o conteúdo CSV dos resultados novos."""
    if not resultados:
        return None

    cols = [
        ("palavra", "Palavra-chave"),
        ("orgao", "Órgão"),
        ("cidade", "Cidade"),
        ("estado", "Estado"),
        ("data_fim", "Data fim"),
        ("item", "Item"),
        ("descricao", "Descrição"),
        ("quantidade", "Quantidade"),
        ("unidade", "Unidade"),
        ("valor_unitario", "Valor unitário"),
        ("valor_total", "Valor total"),
        ("link", "Link"),
    ]

    buf = io.StringIO()
    writer = csv.writer(buf, delimiter=";")
    writer.writerow([label for _, label in cols])

    for r in resultados:
        linha = []
        for key, _ in cols:
            valor = r.get(key, "")
            if key == "data_fim":
                valor = formatar_data(valor)
            linha.append("" if valor is None else valor)
        writer.writerow(linha)

    conteudo = ("﻿" + buf.getvalue()).encode("utf-8")
    print(f"CSV gerado: {len(conteudo)} bytes")
    return conteudo


def enviar_email(html, qtd, csv_bytes=None):
    if not html:
        print("Nenhum item novo. E-mail não enviado.")
        return

    params = {
        "from": "PNCP Monitor <onboarding@resend.dev>",
        "to": [EMAIL_DESTINO],
        "subject": f"[PNCP] {datetime.now().strftime('%d/%m/%Y')} - {qtd} nova(s) licitação(ões)",
        "html": html,
    }

    if csv_bytes:
        params["attachments"] = [
            {
                "filename": f"editais_pncp_{datetime.now().strftime('%Y%m%d')}.csv",
                "content": base64.b64encode(csv_bytes).decode("utf-8"),
            }
        ]
        print(f"Anexo CSV adicionado ao e-mail ({len(csv_bytes)} bytes).")

    try:
        result = resend.Emails.send(params)
        print("E-mail enviado com sucesso:", result)
    except Exception as e:
        print("ERRO ao enviar e-mail:", e)
        raise


if __name__ == "__main__":
    print("Iniciando monitoramento...")
    vistos = carregar_vistos()
    print(f"Itens já vistos anteriormente: {len(vistos)}")

    resultados = buscar_todas()
    print(f"Total encontrado agora: {len(resultados)}")

    # Filtra só os novos
    novos = []
    for r in resultados:
        uid = id_unico(r)
        if uid not in vistos:
            novos.append(r)
            vistos.add(uid)

    print(f"Itens NOVOS: {len(novos)}")

    html = montar_html(novos)
    csv_bytes = gerar_csv(novos)
    enviar_email(html, len(novos), csv_bytes)

    salvar_vistos(vistos)
    print("Lista de itens vistos atualizada.")
    print("Monitoramento finalizado.")