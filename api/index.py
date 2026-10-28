"""
Função serverless do Vercel.

Um único endpoint `/api?acao=...` evita problemas com rewrites que alteram
o caminho visto pela função. As ações são:

    /api?acao=lojas
    /api?acao=pesquisa&q=leite&fontes=continente,auchan
    /api?acao=ofertas&fonte=kuantokusta&url=...&preco=...&nome=...
"""

from __future__ import annotations

import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

from flask import Flask, jsonify, request  # noqa: E402

import logica  # noqa: E402
import providers as prov  # noqa: E402

app = Flask(__name__)
app.json.ensure_ascii = False
app.json.sort_keys = False


def _fontes(pedido: str) -> list[str]:
    pedidas = [f.strip() for f in (pedido or "").split(",") if f.strip()]
    validas = [f for f in pedidas if f in prov.FORNECEDORES]
    return validas or list(prov.FORNECEDORES)


@app.get("/api")
def api():
    acao = (request.args.get("acao") or "lojas").strip().lower()

    if acao == "lojas":
        return jsonify({"lojas": logica.listar_fornecedores()})

    if acao == "pesquisa":
        termo = (request.args.get("q") or "").strip()
        if len(termo) < 2:
            return jsonify({"erro": "Escreve pelo menos 2 caracteres."}), 400
        return jsonify(logica.pesquisar(termo, _fontes(request.args.get("fontes", ""))))

    if acao == "ofertas":
        fonte = request.args.get("fonte", "")
        if fonte not in prov.FORNECEDORES:
            return jsonify({"erro": "Fornecedor inválido."}), 400
        try:
            preco = float(request.args.get("preco", "0") or 0)
        except ValueError:
            return jsonify({"erro": "Preço inválido."}), 400
        return jsonify(logica.obter_ofertas(
            fonte,
            request.args.get("url", ""),
            preco,
            request.args.get("nome", ""),
        ))

    return jsonify({"erro": f"Ação desconhecida: {acao}"}), 404


@app.errorhandler(prov.FornecedorIndisponivel)
def _site_indisponivel(erro):
    return jsonify({"erro": f"Site indisponível: {erro}"}), 502


@app.errorhandler(Exception)
def _erro_interno(erro):  # noqa: BLE001
    return jsonify({"erro": f"Erro interno: {type(erro).__name__}: {erro}"}), 500


@app.get("/")
def raiz():
    return jsonify({
        "app": "Comparador de Preços PT",
        "api": "/api?acao=lojas|pesquisa|ofertas",
    })
