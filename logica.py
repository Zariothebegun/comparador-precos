"""
Lógica partilhada entre o servidor local (`app.py`) e a função do Vercel
(`api/index.py`).

Aqui vive a cache e as funções que falam com os fornecedores. Não há aqui
nada específico de HTTP: cada entrada devolve um dicionário pronto a
serializar em JSON.
"""

from __future__ import annotations

import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any

import providers as prov

CACHE_TTL = 600  # segundos
MAX_POR_FONTE = 60

_cache: dict[str, tuple[float, Any]] = {}
_trava = threading.Lock()


def cache_obter(chave: str):
    with _trava:
        item = _cache.get(chave)
        if not item:
            return None
        quando, valor = item
        if time.time() - quando > CACHE_TTL:
            _cache.pop(chave, None)
            return None
        return valor


def cache_guardar(chave: str, valor):
    with _trava:
        if len(_cache) > 300:
            _cache.clear()
        _cache[chave] = (time.time(), valor)


def listar_fornecedores() -> list[dict]:
    """Metadados das fontes disponíveis (para os chips do frontend)."""
    return [
        {
            "chave": chave,
            "nome": fornecedor.nome,
            "cor": fornecedor.cor,
            "detalhe": chave == prov.KuantoKusta.chave,
        }
        for chave, fornecedor in prov.FORNECEDORES.items()
    ]


def pesquisar(termo: str, fontes: list[str]) -> dict:
    chave = f"p:{termo.lower()}:{','.join(sorted(fontes))}"
    guardado = cache_obter(chave)
    if guardado is not None:
        return guardado  # type: ignore[return-value]

    inicio = time.perf_counter()
    resultados: list[dict] = []
    estado: dict[str, dict] = {}

    with ThreadPoolExecutor(max_workers=len(fontes) or 1) as executor:
        futuros = {}
        for nome in fontes:
            try:
                futuros[executor.submit(prov.obter(nome).pesquisar, termo)] = nome
            except KeyError:
                estado[nome] = {"ok": False, "erro": "fornecedor desconhecido", "n": 0, "ms": 0}

        for futuro in as_completed(futuros):
            nome = futuros[futuro]
            t0 = time.perf_counter()
            try:
                itens = futuro.result()
                mostrados = itens[:MAX_POR_FONTE]
                for item in mostrados:
                    resultados.append(item.como_dict())
                estado[nome] = {
                    "ok": True,
                    "erro": None,
                    "n": len(mostrados),
                    "ms": int((time.perf_counter() - t0) * 1000),
                }
            except Exception as e:  # noqa: BLE001
                estado[nome] = {
                    "ok": False,
                    "erro": str(e)[:220],
                    "n": 0,
                    "ms": int((time.perf_counter() - t0) * 1000),
                }

    resultados.sort(key=lambda r: r["preco"])
    resposta = {
        "query": termo,
        "resultados": resultados,
        "fontes": estado,
        "tempo_ms": int((time.perf_counter() - inicio) * 1000),
        "cache": False,
    }
    cache_guardar(chave, resposta)
    return resposta


def obter_ofertas(fonte: str, url: str, preco: float, nome: str) -> dict:
    chave = f"o:{fonte}:{url}:{preco}"
    guardado = cache_obter(chave)
    if guardado is not None:
        return guardado  # type: ignore[return-value]

    fornecedor = prov.obter(fonte)
    alvo = prov.Resultado(
        fonte=fonte,
        id="",
        nome=nome,
        preco=preco,
        url=url,
        detalhe=(fonte == prov.KuantoKusta.chave),
    )
    ofertas = fornecedor.ofertas(alvo)

    resposta = {
        "fonte": fornecedor.nome,
        "produto": nome,
        "ofertas": [o.como_dict() for o in ofertas],
        "mais_barato": ofertas[0].como_dict() if ofertas else None,
        "mais_caro": ofertas[-1].como_dict() if ofertas else None,
        "poupanca": round(ofertas[-1].preco - ofertas[0].preco, 2) if len(ofertas) > 1 else 0,
    }
    cache_guardar(chave, resposta)
    return resposta
