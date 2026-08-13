# Guia de Uso — Plataforma de Busca de Editais do PNCP

Este guia explica, de forma simples, o que é o projeto e como colocá-lo
no ar — seja no seu próprio computador, seja em um servidor seu.

Você **não precisa ser programador** para seguir este passo a passo.

---

## 1. O que é

Uma plataforma web que busca editais no portal do PNCP (Portal Nacional de
Contratações Públicas) e mostra os resultados numa tabela organizada, com
opção de exportar para planilha (Excel).

Pontos importantes:

- **Não usa banco de dados.** Os dados vêm direto do PNCP, sempre atualizados.
- **Não depende de nenhum serviço pago.** Roda em qualquer lugar com Python.
- **O código é todo seu.** Você pode hospedar onde quiser, quantas vezes quiser.

---

## 2. Do que você precisa

Apenas o **Python** instalado (versão 3.10 ou mais nova). É gratuito.

- Download: https://www.python.org/downloads/
- No Windows, ao instalar, marque a caixinha **"Add Python to PATH"**.

Para conferir se já tem, abra o terminal e digite:

```
python --version
```

Se aparecer algo como `Python 3.12.x`, está tudo certo.

---

## 3. Como rodar (passo a passo)

> Faça isso dentro da pasta do projeto (a pasta que contém o arquivo `app.py`).

### Passo 1 — Instalar as dependências (só na primeira vez)

```
pip install -r requirements.txt
```

### Passo 2 — Iniciar a plataforma

```
python app.py
```

Vai aparecer uma mensagem dizendo que está rodando em `http://localhost:5000`.

### Passo 3 — Abrir no navegador

Abra o navegador e acesse:

```
http://localhost:5000
```

Pronto! É só usar: digite a palavra-chave, escolha os filtros e clique em **Buscar**.

> Para desligar, volte ao terminal e pressione **Ctrl + C**.

---

## 4. Rodar em um servidor seu (para ficar no ar 24h)

Se você tem um servidor próprio (uma VPS na Hostinger, Contabo, DigitalOcean,
etc.), o processo é o mesmo dos passos acima, mas usando um "motor" mais
robusto que o Python sozinho, chamado **gunicorn** (em servidores Linux):

```
pip install -r requirements.txt
gunicorn app:app --bind 0.0.0.0:5000
```

Depois é só apontar o seu domínio/IP para a porta 5000. Se quiser, eu te
ajudo a fazer essa configuração quando precisar.

> Em servidores Windows, pode usar `python app.py` mesmo.

---

## 5. E se o servidor atual (Render) sair do ar?

Sem problema. Como o código é todo seu e padrão, basta subir o mesmo
projeto em outro lugar. Algumas opções gratuitas além do Render:

- **Railway** — https://railway.app
- **Fly.io** — https://fly.io
- **PythonAnywhere** — https://www.pythonanywhere.com

Ou no seu próprio servidor (seção 4 acima). O código não muda.

---

## 6. Estrutura dos arquivos

```
app.py             O "cérebro" da aplicação (busca no PNCP)
static/index.html  A página que você vê no navegador
requirements.txt   Lista do que precisa ser instalado
render.yaml        Configuração para o Render (deploy automático)
Procfile           Comando de inicialização (Render/Railway)
README.md          Resumo técnico
GUIA_DE_USO.md     Este guia
```

---

## Precisa de ajuda?

Qualquer dúvida na hora de colocar no ar, ou se quiser migrar para outro
servidor, é só me chamar que eu te oriento. 🤝

**WhatsApp:** +1 (646) 326-8046
