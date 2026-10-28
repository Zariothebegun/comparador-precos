"""
Comparador de Preços — Portugal
Servidor local. Sem dependências externas: só a biblioteca padrão do Python.

    uv run python app.py
    uv run python app.py --port 8770 --abrir

A lógica de pesquisa está em `logica.py`, partilhada com a função do Vercel
(`api/index.py`).
"""

from __future__ import annotations

import argparse
import json
import mimetypes
import threading
import urllib.parse
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import logica
import providers as prov

RAIZ = Path(__file__).resolve().parent
WEB = RAIZ / "web"


def _fontes(pedido: str) -> list[str]:
    pedidas = [f.strip() for f in (pedido or "").split(",") if f.strip()]
    validas = [f for f in pedidas if f in prov.FORNECEDORES]
    return validas or list(prov.FORNECEDORES)


class Handler(BaseHTTPRequestHandler):
    server_version = "ComparadorPT/1.0"

    def log_message(self, formato, *args):  # silenciar log ruidoso
        pass

    # ---------------- utilidades ----------------

    def _json(self, dados: dict, codigo: int = 200):
        corpo = json.dumps(dados, ensure_ascii=False).encode("utf-8")
        self.send_response(codigo)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(corpo)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(corpo)

    def _ficheiro(self, caminho: Path):
        if not caminho.is_file():
            self.send_error(404, "Não encontrado")
            return
        tipo, _ = mimetypes.guess_type(str(caminho))
        corpo = caminho.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", (tipo or "application/octet-stream") + "; charset=utf-8")
        self.send_header("Content-Length", str(len(corpo)))
        self.send_header("Cache-Control", "no-store, must-revalidate")
        self.end_headers()
        self.wfile.write(corpo)

    # ---------------- rotas ----------------

    def do_GET(self):  # noqa: N802
        partes = urllib.parse.urlsplit(self.path)
        rota = partes.path
        qs = urllib.parse.parse_qs(partes.query)
        valor = lambda nome, padrao="": (qs.get(nome, [padrao])[0] or padrao)

        try:
            # ---- endpoint único (o mesmo que o Vercel usa) ----
            if rota == "/api":
                acao = valor("acao", "lojas").strip().lower()

                if acao == "lojas":
                    self._json({"lojas": logica.listar_fornecedores()})
                    return

                if acao == "pesquisa":
                    termo = valor("q").strip()
                    if len(termo) < 2:
                        self._json({"erro": "Escreve pelo menos 2 caracteres."}, 400)
                        return
                    self._json(logica.pesquisar(termo, _fontes(valor("fontes"))))
                    return

                if acao == "ofertas":
                    fonte = valor("fonte")
                    if fonte not in prov.FORNECEDORES:
                        self._json({"erro": "Fornecedor inválido."}, 400)
                        return
                    try:
                        preco = float(valor("preco", "0") or 0)
                    except ValueError:
                        self._json({"erro": "Preço inválido."}, 400)
                        return
                    self._json(logica.obter_ofertas(
                        fonte, valor("url"), preco, valor("nome"),
                    ))
                    return

                self._json({"erro": f"Ação desconhecida: {acao}"}, 404)
                return

            # ---- rotas antigas (compatibilidade) ----
            if rota == "/api/lojas":
                self._json({"lojas": logica.listar_fornecedores()})
                return

            if rota == "/api/pesquisa":
                termo = valor("q").strip()
                if len(termo) < 2:
                    self._json({"erro": "Escreve pelo menos 2 caracteres."}, 400)
                    return
                self._json(logica.pesquisar(termo, _fontes(valor("fontes"))))
                return

            if rota == "/api/ofertas":
                fonte = valor("fonte")
                if fonte not in prov.FORNECEDORES:
                    self._json({"erro": "Fornecedor inválido."}, 400)
                    return
                try:
                    preco = float(valor("preco", "0") or 0)
                except ValueError:
                    self._json({"erro": "Preço inválido."}, 400)
                    return
                self._json(logica.obter_ofertas(fonte, valor("url"), preco, valor("nome")))
                return

            # ---- estáticos ----
            if rota in ("/", ""):
                self._ficheiro(WEB / "index.html")
                return

            alvo = (WEB / rota.lstrip("/")).resolve()
            if WEB in alvo.parents or alvo.parent == WEB:
                self._ficheiro(alvo)
            else:
                self.send_error(403)

        except prov.FornecedorIndisponivel as e:
            self._json({"erro": f"Site indisponível: {e}"}, 502)
        except KeyError as e:
            self._json({"erro": str(e)}, 400)
        except Exception as e:  # noqa: BLE001
            self._json({"erro": f"Erro interno: {type(e).__name__}: {e}"}, 500)


# --------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Comparador de preços PT")
    parser.add_argument("--port", type=int, default=8770)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--abrir", action="store_true", help="abrir o browser ao arrancar")
    args = parser.parse_args()

    servidor = ThreadingHTTPServer((args.host, args.port), Handler)
    endereco = f"http://{args.host}:{args.port}/"
    print(f"Comparador de Preços a correr em {endereco}")
    print("Ctrl+C para parar.")

    if args.abrir:
        threading.Timer(1.0, lambda: webbrowser.open(endereco)).start()

    try:
        servidor.serve_forever()
    except KeyboardInterrupt:
        print("\nA encerrar...")
    finally:
        servidor.server_close()


if __name__ == "__main__":
    main()
