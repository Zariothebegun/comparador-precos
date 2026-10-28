# Comparador de Preços · Portugal

App local que pesquisa um produto em várias lojas portuguesas, mostra o preço em
cada uma e diz qual é a **mais barata**.

Corre no teu PC, abre no browser e não precisa de conta nem de instalação de
programas com direitos de administrador.

---

## Como arrancar

Duplo clique em **`run.cmd`**.

Ou, no terminal (dentro desta pasta):

```bat
uv run --no-project --python 3.14 python app.py --abrir
```

Depois abre <http://127.0.0.1:8770/>.

Para parar: `Ctrl+C` no terminal, ou fecha a janela.

### Requisitos

- Windows com `uv` instalado (`%USERPROFILE%\.local\bin\uv.exe`).
- Python 3.14 gerido pelo `uv` (`uv python install 3.14`).
- Nada mais: o servidor usa apenas a biblioteca padrão do Python.

---

## O que faz

1. Escreves o nome de um produto (ex.: `leite`, `iphone 17e`, `airfryer`).
2. A app consulta as lojas ativas em paralelo.
3. Mostra um cartão por artigo, com os mais relevantes primeiro (podes mudar
   a ordenação para preço, nº de lojas ou nome).
4. No topo dos resultados aparece **“Mais barato: X €”**, calculado entre os
   artigos mais relevantes da pesquisa.
5. Nos artigos com várias lojas, o botão **Ver N lojas** abre um painel com a
   tabela de preços loja a loja, a mais barata destacada e a poupança face à
   mais cara.

Podes ligar/desligar lojas nos botões do topo (a escolha fica guardada).
Resultados ficam em cache 10 minutos para não estar sempre a bater nos sites.

A ordenação por **relevância** dá prioridade a nomes que começam pelo termo
pesquisado e penaliza acessórios (capas, películas, cabos…), para uma pesquisa
como `iphone 17e` não abrir com uma capa de 47 €.

---

## Lojas cobertas

| Fonte | Tipo | O que dá |
|---|---|---|
| **Continente** | supermercado | preço do artigo no Continente |
| **Auchan** | supermercado | preço do artigo no Auchan |
| **Globaldata** | eletrónica | preço do artigo na Globaldata |
| **KuantoKusta** | comparador | preço mínimo **e lista de lojas** (20+ lojas por artigo) |

O KuantoKusta é a peça central para “preço em cada loja”: agrega lojas como
Worten, Fnac, Radio Popular, iCase, FTShopping, Smartmobile, entre outras.
As outras três fontes dão preços diretos de supermercado e eletrónica.

### Lojas testadas que **não** entram (e porquê)

| Loja | Resultado |
|---|---|
| Worten | página responde, mas os produtos só aparecem com JavaScript |
| Fnac | 403 Forbidden mesmo com cliente que imita o Chrome |
| Intermarché | pesquisa devolve 404 (site sem pesquisa pública) |
| PcDiga | pesquisa carregada por JavaScript |
| Lidl | API interna devolve 401/400 sem token |
| Pingo Doce | redireciona a pesquisa para `/receitas/`, sem preços |
| Minipreço | domínio não resolve |

Não existe nenhuma API pública que devolva os preços de **todas** as lojas
portuguesas. A app cobre o que é tecnicamente acessível e mostra, sem esconder,
quando uma fonte falha.

---

## Limitações honestas

- **Não há API oficial.** Os dados são lidos do HTML/JSON que os sites enviam ao
  browser. Se um site mudar o layout, o parser respetivo parte. A app mostra o
  erro na barra de estado em vez de fingir que não há resultados.
- **Preços não normalizados por unidade.** Um pacote de 6×1 L aparece ao lado de
  uma garrafa de 1 L; o preço mais baixo pode não ser o melhor negócio por litro.
- **Portes e stock** podem alterar o custo final. Confirma sempre no site da loja.
- **Uso pessoal e moderado.** Não faças pesquisas em massa: os sites podem
  bloquear o teu IP.
- Os preços do KuantoKusta têm a data do último teste da própria plataforma.

---

## Estrutura

```
comparador-precos/
├── app.py                  servidor HTTP local (stdlib)
├── logica.py               cache + pesquisa (partilhado com o Vercel)
├── providers.py            parsers: Continente, Auchan, Globaldata, KuantoKusta
├── api/
│   └── index.py            função serverless (Flask) para o Vercel
├── requirements.txt        dependência do Vercel (Flask)
├── vercel.json             rewrites + configuração da função
├── teste_fornecedores.py   teste rápido dos parsers no terminal
├── run.cmd                 atalho para arrancar no Windows
└── web/
    ├── index.html
    ├── app.js
    └── styles.css
```

### API

O frontend usa um único endpoint, igual em local e no Vercel:

| Rota | Descrição |
|---|---|
| `GET /api?acao=lojas` | fontes disponíveis |
| `GET /api?acao=pesquisa&q=leite&fontes=continente,auchan` | pesquisa |
| `GET /api?acao=ofertas&fonte=kuantokusta&url=…&preco=…&nome=…` | preços por loja |

As rotas antigas (`/api/lojas`, `/api/pesquisa`, `/api/ofertas`) continuam a
funcionar no servidor local.

### Testar os parsers

```bat
uv run --no-project --python 3.14 teste_fornecedores.py
```

---

## Publicar no Vercel

O projeto está preparado para o Vercel:

- `api/index.py` é a função Python (Flask) que responde em `/api`.
- `web/` é servido como estático; `vercel.json` mapeia `/`, `/app.js` e
  `/styles.css`.
- `requirements.txt` instala o Flask no build.

Fluxo recomendado (sem instalar nada):

1. Cria um repositório vazio no GitHub.
2. Envia esta pasta para o repositório.
3. Em <https://vercel.com/new>, importa o repositório.
4. Framework preset: **Other**. Deploy.

O endereço público fica no formato `https://<projeto>.vercel.app`.

**Nota:** o Vercel corre a função a partir dos IPs dele. Se alguma loja
bloquear esses IPs, o erro aparece na barra de estado por fonte — não é
escondido nem substituído por dados falsos.

---

## Aviso

Projeto escolar. Os nomes e marcas das lojas pertencem aos respetivos donos.
