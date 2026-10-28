"""
Fornecedores de preços.

Cada fornecedor expõe:
    pesquisar(termo) -> list[Resultado]
    ofertas(resultado) -> list[Oferta]

Nota: estes sites não têm API pública. Os dados são lidos do HTML que os
próprios sites enviam ao browser. Se um site mudar o layout, o parser
correspondente tem de ser ajustado — o erro aparece na interface, nunca em
silêncio.
"""

from __future__ import annotations

import gzip
import html as html_lib
import json
import re
import ssl
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field, asdict
from typing import Any

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/155.0.0.0 Safari/537.36"
)

_CABECALHOS = {
    "User-Agent": UA,
    "Accept": "text/html,application/xhtml+xml,application/json;q=0.9,*/*;q=0.8",
    "Accept-Language": "pt-PT,pt;q=0.9,en;q=0.7",
    "Accept-Encoding": "gzip",
    "Cache-Control": "no-cache",
}

_CTX = ssl.create_default_context()


class FornecedorIndisponivel(Exception):
    """O site não respondeu ou mudou de estrutura."""


# --------------------------------------------------------------------------
# Modelos
# --------------------------------------------------------------------------

@dataclass
class Resultado:
    fonte: str
    id: str
    nome: str
    preco: float
    url: str = ""
    marca: str = ""
    imagem: str = ""
    lojas: int = 1
    preco_max: float | None = None
    tipo: str = "produto"       # "produto" | "comparador"
    detalhe: bool = False        # tem lista de lojas?

    def como_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class Oferta:
    loja: str
    preco: float
    url: str = ""
    preco_antigo: float | None = None
    envio: str = ""
    atualizado: str = ""
    destaque: bool = False

    def como_dict(self) -> dict[str, Any]:
        return asdict(self)


# --------------------------------------------------------------------------
# HTTP
# --------------------------------------------------------------------------

def buscar_html(url: str, timeout: int = 20, tentativas: int = 2) -> str:
    ultimo_erro: Exception | None = None
    for n in range(tentativas):
        try:
            pedido = urllib.request.Request(url, headers=_CABECALHOS)
            with urllib.request.urlopen(pedido, timeout=timeout, context=_CTX) as r:
                bruto = r.read()
                if r.headers.get("Content-Encoding") == "gzip":
                    bruto = gzip.decompress(bruto)
                charset = "utf-8"
                ct = r.headers.get("Content-Type", "")
                if "charset=" in ct:
                    charset = ct.split("charset=")[-1].split(";")[0].strip()
                return bruto.decode(charset, "replace")
        except urllib.error.HTTPError as e:
            ultimo_erro = e
            if e.code in (403, 429):
                break
        except Exception as e:  # noqa: BLE001
            ultimo_erro = e
        time.sleep(0.6 * (n + 1))
    raise FornecedorIndisponivel(f"{type(ultimo_erro).__name__}: {ultimo_erro}")


def _num(valor: Any) -> float | None:
    if valor is None or valor == "":
        return None
    if isinstance(valor, (int, float)):
        return float(valor)
    texto = str(valor).strip().replace("€", "").replace(" ", "")
    if "," in texto and "." in texto:
        texto = texto.replace(".", "").replace(",", ".")
    elif "," in texto:
        texto = texto.replace(",", ".")
    try:
        return float(texto)
    except ValueError:
        return None


def _texto(valor: str) -> str:
    return html_lib.unescape(valor or "").strip()


def _next_data(html: str) -> dict:
    m = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', html, re.S)
    if not m:
        raise FornecedorIndisponivel("__NEXT_DATA__ não encontrado (layout mudou?)")
    return json.loads(m.group(1))


# --------------------------------------------------------------------------
# Continente
# --------------------------------------------------------------------------

class Continente:
    nome = "Continente"
    chave = "continente"
    cor = "#e30613"

    URL = "https://www.continente.pt/pesquisa/?q={q}"

    def pesquisar(self, termo: str) -> list[Resultado]:
        url = self.URL.format(q=urllib.parse.quote_plus(termo))
        pagina = buscar_html(url)
        itens: list[Resultado] = []
        vistos: set[str] = set()

        # mapa id -> URL do produto, numa única passagem pela página
        links: dict[str, str] = {}
        for lm in re.finditer(r'href="([^"]*?/produto/[^"]+?\.html)"', pagina):
            href = lm.group(1)
            pid_m = re.search(r"-(\d+)\.html$", href)
            if pid_m:
                links[pid_m.group(1)] = href

        for m in re.finditer(r"data-product-tile-impression='([^']+)'", pagina):
            bruto = m.group(1).replace("&quot;", '"').replace("&amp;", "&")
            try:
                dados = json.loads(bruto)
            except json.JSONDecodeError:
                continue

            pid = str(dados.get("id") or "")
            if not pid or pid in vistos:
                continue
            vistos.add(pid)

            preco = _num(dados.get("price"))
            if preco is None:
                continue

            href = links.get(pid)
            if href:
                url_item = href if href.startswith("http") else "https://www.continente.pt" + href
            else:
                url_item = url

            itens.append(Resultado(
                fonte=self.chave,
                id=pid,
                nome=_texto(str(dados.get("name", ""))),
                preco=preco,
                url=url_item,
                marca=_texto(str(dados.get("brand", ""))),
                lojas=1,
                tipo="produto",
                detalhe=False,
            ))

        return itens

    def ofertas(self, resultado: Resultado) -> list[Oferta]:
        return [Oferta(loja=self.nome, preco=resultado.preco, url=resultado.url)]


# --------------------------------------------------------------------------
# Auchan
# --------------------------------------------------------------------------

class Auchan:
    nome = "Auchan"
    chave = "auchan"
    cor = "#e2001a"

    URL = "https://www.auchan.pt/pt/pesquisa?q={q}"

    def pesquisar(self, termo: str) -> list[Resultado]:
        url = self.URL.format(q=urllib.parse.quote_plus(termo))
        pagina = buscar_html(url)
        itens: list[Resultado] = []
        vistos: set[str] = set()

        for m in re.finditer(r'data-gtm="([^"]+)"', pagina):
            bruto = m.group(1).replace("&quot;", '"').replace("&amp;", "&")
            try:
                dados = json.loads(bruto)
            except json.JSONDecodeError:
                continue

            pid = str(dados.get("id") or "")
            if not pid or pid in vistos:
                continue
            vistos.add(pid)

            preco = _num(dados.get("price"))
            if preco is None:
                continue

            trecho = pagina[max(0, m.start() - 4000):m.start() + 200]
            link = re.search(r'&quot;absoluteProductUrl&quot;:&quot;([^&]+)&quot;', trecho)
            if not link:
                link_rel = re.search(r'href="(/pt/[^"]+?\.html)"', pagina[m.start():m.start() + 8000])
                href = "https://www.auchan.pt" + link_rel.group(1) if link_rel else url
            else:
                href = link.group(1)

            itens.append(Resultado(
                fonte=self.chave,
                id=pid,
                nome=_texto(str(dados.get("name", ""))).title(),
                preco=preco,
                url=href,
                marca=_texto(str(dados.get("brand", ""))),
                lojas=1,
                tipo="produto",
                detalhe=False,
            ))

        return itens

    def ofertas(self, resultado: Resultado) -> list[Oferta]:
        return [Oferta(loja=self.nome, preco=resultado.preco, url=resultado.url)]


# --------------------------------------------------------------------------
# Globaldata (eletrónica)
# --------------------------------------------------------------------------

class Globaldata:
    nome = "Globaldata"
    chave = "globaldata"
    cor = "#c8102e"

    URL = "https://www.globaldata.pt/search?q={q}"

    def pesquisar(self, termo: str) -> list[Resultado]:
        url = self.URL.format(q=urllib.parse.quote_plus(termo))
        pagina = buscar_html(url)
        itens: list[Resultado] = []
        vistos: set[str] = set()

        for bloco in re.split(r'<div class="product-tile-row">', pagina)[1:]:
            nome_m = re.search(
                r'data-qa="product-tile-name-link"[^>]*>\s*(.*?)\s*</a>', bloco, re.S
            )
            if not nome_m:
                continue

            preco_m = re.search(
                r'class="sales js-sales"[^>]*>.*?class="value" content="([\d.]+)"',
                bloco, re.S,
            ) or re.search(r'class="value" content="([\d.]+)"', bloco)
            preco = _num(preco_m.group(1)) if preco_m else None
            if preco is None:
                continue

            link_m = re.search(r'href="(/[^"]+?\.html)"', bloco)
            caminho = link_m.group(1) if link_m else ""
            if not caminho or caminho in vistos:
                continue
            vistos.add(caminho)

            img_m = re.search(
                r'<div class="image-container[^"]*">.*?<img[^>]+src="([^"]+)"',
                bloco, re.S,
            )

            itens.append(Resultado(
                fonte=self.chave,
                id=caminho.rsplit("/", 1)[-1].replace(".html", ""),
                nome=_texto(re.sub(r"\s+", " ", nome_m.group(1))),
                preco=preco,
                url="https://www.globaldata.pt" + caminho,
                imagem=html_lib.unescape(img_m.group(1)) if img_m else "",
                lojas=1,
                tipo="produto",
                detalhe=False,
            ))

        return itens

    def ofertas(self, resultado: Resultado) -> list[Oferta]:
        return [Oferta(loja=self.nome, preco=resultado.preco, url=resultado.url)]


# --------------------------------------------------------------------------
# KuantoKusta (comparador — preços por loja)
# --------------------------------------------------------------------------

class KuantoKusta:
    nome = "KuantoKusta"
    chave = "kuantokusta"
    cor = "#0d6efd"

    BASE = "https://www.kuantokusta.pt"
    URL = BASE + "/search?q={q}"

    def pesquisar(self, termo: str) -> list[Resultado]:
        url = self.URL.format(q=urllib.parse.quote_plus(termo))
        dados = _next_data(buscar_html(url))
        base = dados.get("props", {}).get("pageProps", {}).get("basePage", {})
        produtos = base.get("data") or []

        itens: list[Resultado] = []
        for p in produtos:
            preco = _num(p.get("priceMin"))
            if preco is None:
                continue

            imagens = p.get("images") or []
            imagem = ""
            if imagens:
                primeira = imagens[0]
                if isinstance(primeira, str):
                    imagem = primeira
                elif isinstance(primeira, dict):
                    imagem = primeira.get("url") or primeira.get("src") or ""

            caminho = p.get("url") or ""
            itens.append(Resultado(
                fonte=self.chave,
                id=str(p.get("id") or ""),
                nome=_texto(str(p.get("name", ""))),
                preco=preco,
                url=self.BASE + caminho if caminho.startswith("/") else caminho,
                marca=_texto(str(p.get("brand", "") or "")),
                imagem=imagem,
                lojas=int(p.get("totalOffers") or 1),
                preco_max=_num(p.get("priceMax")),
                tipo="comparador",
                detalhe=True,
            ))

        return itens

    def ofertas(self, resultado: Resultado) -> list[Oferta]:
        if not resultado.url:
            return []

        dados = _next_data(buscar_html(resultado.url))
        produto = (
            dados.get("props", {}).get("pageProps", {}).get("basePage", {}).get("product", {})
        )
        brutas = produto.get("offers") or []

        ofertas: list[Oferta] = []
        for o in brutas:
            preco = _num(o.get("price"))
            if preco is None:
                continue

            envio = ""
            transporte = o.get("shipping")
            filtros = o.get("filters") or {}
            if isinstance(transporte, dict):
                preco_envio = _num(transporte.get("minimumPrice"))
                if filtros.get("isFreeShipping") or preco_envio == 0:
                    envio = "Grátis"
                elif preco_envio:
                    envio = f"desde {preco_envio:.2f} €".replace(".", ",")
            elif transporte:
                envio = str(transporte)

            atualizado = str(o.get("lastCheckedAt") or "")[:10]

            ofertas.append(Oferta(
                loja=_texto(str(o.get("storeName") or "Loja")),
                preco=preco,
                url=str(o.get("url") or ""),
                preco_antigo=_num(o.get("oldPrice")) or None,
                envio=envio,
                atualizado=atualizado,
                destaque=bool(o.get("isHighlighted")),
            ))

        ofertas.sort(key=lambda x: x.preco)
        return ofertas


# --------------------------------------------------------------------------
# Registo
# --------------------------------------------------------------------------

FORNECEDORES: dict[str, Any] = {
    Continente.chave: Continente(),
    Auchan.chave: Auchan(),
    Globaldata.chave: Globaldata(),
    KuantoKusta.chave: KuantoKusta(),
}


def obter(chave: str):
    fornecedor = FORNECEDORES.get(chave)
    if not fornecedor:
        raise KeyError(f"Fornecedor desconhecido: {chave}")
    return fornecedor
