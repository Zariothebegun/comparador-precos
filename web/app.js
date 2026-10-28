/* =========================================================
   Comparador de Preços — interface
   ========================================================= */

(() => {
  "use strict";

  const eur = new Intl.NumberFormat("pt-PT", { style: "currency", currency: "EUR" });
  const dinheiro = (v) => (typeof v === "number" && Number.isFinite(v) ? eur.format(v) : "—");

  const $ = (id) => document.getElementById(id);

  const ui = {
    fontes: $("fontes"),
    form: $("form"),
    q: $("q"),
    btn: $("btn"),
    estado: $("estado"),
    resultados: $("resultados"),
    vazio: $("vazio"),
    sugestoes: $("sugestoes"),
    gaveta: $("gaveta"),
    gavetaFundo: $("gavetaFundo"),
    gavetaCorpo: $("gavetaCorpo"),
    gavetaTitulo: $("gavetaTitulo"),
    fechar: $("fechar"),
  };

  const app = {
    lojas: [],
    ativas: new Set(),
    dados: null,
    visiveis: [],
    ordem: "relevancia",
    controlador: null,
    focoAnterior: null,
    pedidoOfertas: null,
  };

  const esc = (v) =>
    String(v ?? "").replace(/[&<>"']/g, (c) => ({
      "&": "&amp;",
      "<": "&lt;",
      ">": "&gt;",
      '"': "&quot;",
      "'": "&#39;",
    })[c]);

  const iconeCaixa = `
    <svg viewBox="0 0 24 24" width="26" height="26" fill="none" stroke="currentColor" stroke-width="1.4">
      <path d="M3 8l9-5 9 5v8l-9 5-9-5z" stroke-linejoin="round"/>
      <path d="M3 8l9 5 9-5M12 13v8" stroke-linejoin="round"/>
    </svg>`;

  const dataCurta = (iso) => {
    if (!iso) return "—";
    const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(String(iso));
    return m ? `${m[3]}/${m[2]}/${m[1]}` : String(iso);
  };

  /* ---------- aviso rápido ---------- */

  function aviso(texto) {
    const caixa = document.createElement("div");
    caixa.className = "aviso";
    caixa.textContent = texto;
    document.body.appendChild(caixa);
    setTimeout(() => caixa.classList.add("visivel"), 2200);
    setTimeout(() => caixa.remove(), 2700);
  }

  /* ---------- fontes / chips ---------- */

  function desenharFontes() {
    if (!app.lojas.length) {
      ui.fontes.innerHTML = '<span class="fonte-chip" aria-disabled="true">Sem ligação ao servidor</span>';
      return;
    }

    ui.fontes.innerHTML = app.lojas
      .map(
        (l) => `
        <button type="button" class="fonte-chip" data-chave="${esc(l.chave)}"
                aria-pressed="${app.ativas.has(l.chave)}"
                title="Incluir ${esc(l.nome)} na pesquisa">${esc(l.nome)}</button>`
      )
      .join("");
  }

  function alternarFonte(chave) {
    if (app.ativas.has(chave)) {
      if (app.ativas.size === 1) {
        aviso("Tem de ficar pelo menos uma loja ativa.");
        return;
      }
      app.ativas.delete(chave);
    } else {
      app.ativas.add(chave);
    }

    const botao = ui.fontes.querySelector(`[data-chave="${CSS.escape(chave)}"]`);
    if (botao) botao.setAttribute("aria-pressed", String(app.ativas.has(chave)));

    try {
      localStorage.setItem("comparador.fontes", JSON.stringify([...app.ativas]));
    } catch {
      /* modo privado — ignora */
    }
  }

  /* ---------- estado das fontes ---------- */

  function desenharEstado(dados) {
    const entradas = Object.entries(dados.fontes || {});
    if (!entradas.length) {
      ui.estado.hidden = true;
      return;
    }

    const nomes = new Map(app.lojas.map((l) => [l.chave, l.nome]));

    ui.estado.innerHTML =
      entradas
        .map(([chave, info]) => {
          const nome = nomes.get(chave) || chave;
          if (info.ok) {
            return `<span class="estado-item ok"><span class="ponto"></span>${esc(nome)} · ${info.n} resultado${info.n === 1 ? "" : "s"}</span>`;
          }
          return `<span class="estado-item falha" title="${esc(info.erro || "")}">
              <span class="ponto"></span>${esc(nome)} indisponível
              <span class="motivo">${esc((info.erro || "").slice(0, 70))}</span>
            </span>`;
        })
        .join("") +
      (dados.fontes && dados.fontes.kuantokusta
        ? '<span class="estado-nota">KuantoKusta agrega 20+ lojas por artigo</span>'
        : "");

    ui.estado.hidden = false;
  }

  /* ---------- pesquisa ---------- */

  function esqueletos(n = 5) {
    ui.resultados.innerHTML = Array.from({ length: n }, () => '<div class="esqueleto"></div>').join("");
  }

  function mostrarVazio(titulo, sub) {
    const t = ui.vazio.querySelector(".vazio-titulo");
    const s = ui.vazio.querySelector(".vazio-sub");
    if (t) t.textContent = titulo;
    if (s) s.textContent = sub;
    ui.vazio.hidden = false;
  }

  async function pesquisar(termo) {
    termo = (termo || "").trim();
    if (termo.length < 2) {
      ui.q.focus();
      aviso("Escreve pelo menos 2 caracteres.");
      return;
    }

    if (!app.ativas.size) {
      aviso("Escolhe pelo menos uma loja no topo.");
      return;
    }

    if (app.controlador) app.controlador.abort();
    const ctrl = new AbortController();
    app.controlador = ctrl;

    ui.q.value = termo;
    ui.btn.disabled = true;
    ui.btn.textContent = "A procurar…";
    ui.vazio.hidden = true;
    ui.estado.hidden = true;
    ui.estado.innerHTML = "";
    ui.resultados.innerHTML = "";
    esqueletos();

    const url =
      "/api?acao=pesquisa&q=" +
      encodeURIComponent(termo) +
      "&fontes=" +
      encodeURIComponent([...app.ativas].join(","));

    try {
      const resposta = await fetch(url, { signal: ctrl.signal });
      const dados = await resposta.json().catch(() => ({}));

      if (!resposta.ok) throw new Error(dados.erro || `Erro ${resposta.status}`);

      app.dados = dados;
      desenharEstado(dados);
      desenharResultados();
    } catch (erro) {
      if (erro.name === "AbortError") return;

      ui.resultados.innerHTML = "";
      ui.estado.hidden = true;
      mostrarVazio(
        "Não consegui falar com o servidor",
        "Verifica a tua ligação à internet e tenta outra vez."
      );
      console.error(erro);
    } finally {
      if (app.controlador === ctrl) {
        app.controlador = null;
        ui.btn.disabled = false;
        ui.btn.textContent = "Comparar";
      }
    }
  }

  /* ---------- resultados ---------- */

  // Palavras que costumam indicar acessórios: se o nome as tiver, o artigo
  // desce na relevância (ex.: procurar "iphone 17e" e vir uma capa primeiro).
  const ACESSORIOS = new Set([
    "capa", "capas", "funda", "fundas", "estojo", "bolsa", "mala",
    "pelicula", "peliculas", "protetor", "protecao", "protector",
    "carregador", "cabo", "cabos", "suporte", "adaptador", "bumper",
    "case", "cover", "screen", "ecra", "ecras",
  ]);

  const normalizar = (texto) =>
    String(texto || "")
      .normalize("NFD")
      .replace(/[\u0300-\u036f]/g, "")
      .toLowerCase();

  function pontuar(item, tokens) {
    if (!tokens.length) return 0;

    const nome = normalizar(item.nome);
    const palavras = nome.split(/[^a-z0-9]+/).filter(Boolean);
    const conjunto = new Set(palavras);
    const acertos = tokens.filter((t) => conjunto.has(t) || nome.includes(t)).length;

    let nota = acertos / tokens.length;

    // Bónus se o termo pesquisado aparece cedo no nome ("Leite UHT…" antes de
    // "Pão de Leite"), para o artigo certo ficar à frente.
    let primeira = Infinity;
    for (const t of tokens) {
      const indice = palavras.findIndex((p) => p === t || p.includes(t));
      if (indice >= 0) primeira = Math.min(primeira, indice);
    }
    if (Number.isFinite(primeira)) nota += Math.max(0, 0.3 - 0.05 * Math.min(primeira, 6));

    if ([...ACESSORIOS].some((p) => conjunto.has(p))) nota -= 0.5;
    return nota;
  }

  function ordenar(itens, notas) {
    const copia = [...itens];
    const nota = (item) => notas.get(item) || 0;

    switch (app.ordem) {
      case "preco-asc":
        copia.sort((a, b) => a.preco - b.preco);
        break;
      case "preco-desc":
        copia.sort((a, b) => b.preco - a.preco);
        break;
      case "lojas-desc":
        copia.sort((a, b) => (b.lojas || 1) - (a.lojas || 1) || a.preco - b.preco);
        break;
      case "nome-asc":
        copia.sort((a, b) => a.nome.localeCompare(b.nome, "pt"));
        break;
      default:
        copia.sort((a, b) => nota(b) - nota(a) || a.preco - b.preco);
    }
    return copia;
  }

  function cartao(item, indice, maisBarato) {
    const temLojas = item.tipo === "comparador" && (item.lojas || 0) > 1;
    const selos = [];

    selos.push(`<span class="selo lojas">${esc(nomeFonte(item.fonte))}</span>`);
    if (item.tipo === "comparador" && item.lojas > 0) {
      selos.push(`<span class="selo">${item.lojas} loja${item.lojas === 1 ? "" : "s"}</span>`);
    }
    if (item.marca && normalizar(item.marca) !== normalizar(nomeFonte(item.fonte))) {
      selos.push(`<span class="selo marca">${esc(item.marca)}</span>`);
    }
    if (maisBarato) selos.push('<span class="selo melhor-selo">mais barato</span>');

    const intervalo =
      item.tipo === "comparador" && item.preco_max && item.preco_max > item.preco
        ? `<span class="intervalo">até ${dinheiro(item.preco_max)}</span>`
        : "";

    const acao = temLojas
      ? `<button type="button" class="acao primaria" data-ofertas="${indice}">
           Ver ${item.lojas} lojas
         </button>`
      : item.url
        ? `<a class="acao" href="${esc(item.url)}" target="_blank" rel="noopener noreferrer">Abrir loja</a>`
        : "";

    return `
      <article class="cartao${maisBarato ? " melhor" : ""}" data-indice="${indice}">
        <div class="miniatura">${
          item.imagem
            ? `<img src="${esc(item.imagem)}" alt="" loading="lazy" referrerpolicy="no-referrer">`
            : iconeCaixa
        }</div>
        <div class="info">
          <p class="nome-produto">${esc(item.nome)}</p>
          <div class="meta-linha">
            ${selos.join("")}
            ${intervalo}
          </div>
        </div>
        <div class="preco-bloco">
          <div class="preco${maisBarato ? " de" : ""}">${dinheiro(item.preco)}</div>
          ${acao}
        </div>
      </article>`;
  }

  function nomeFonte(chave) {
    const loja = app.lojas.find((l) => l.chave === chave);
    return loja ? loja.nome : chave;
  }

  function desenharResultados() {
    const dados = app.dados;
    if (!dados) return;

    const itens = dados.resultados || [];

    if (!itens.length) {
      ui.resultados.innerHTML = "";
      mostrarVazio(
        `Sem resultados para “${dados.query}”`,
        "Tenta um nome mais simples ou retira acentos (ex: “cafe” em vez de “café”)."
      );
      return;
    }

    ui.vazio.hidden = true;

    const tokens = normalizar(dados.query)
      .split(/[^a-z0-9]+/)
      .filter((t) => t.length >= 2);
    const notas = new Map(itens.map((i) => [i, pontuar(i, tokens)]));

    app.visiveis = ordenar(itens, notas);

    // Destaque = artigo mais relevante e, dentro desse grupo, o mais barato.
    const notaMax = Math.max(...itens.map((i) => notas.get(i)));
    const relevantes = itens.filter((i) => notas.get(i) === notaMax);
    const melhor = relevantes.reduce((a, b) => (b.preco < a.preco ? b : a));
    const segundos = ((dados.tempo_ms || 0) / 1000).toFixed(1).replace(".", ",");

    const cabecalho = `
      <div class="resumo">
        <span>
          <strong>${itens.length} resultado${itens.length === 1 ? "" : "s"}</strong>
          para “${esc(dados.query)}” · ${segundos} s
        </span>
        <label class="ordem">
          Ordenar
          <select id="ordem">
            <option value="relevancia"${app.ordem === "relevancia" ? " selected" : ""}>relevância</option>
            <option value="preco-asc"${app.ordem === "preco-asc" ? " selected" : ""}>preço (mais baixo)</option>
            <option value="preco-desc"${app.ordem === "preco-desc" ? " selected" : ""}>preço (mais alto)</option>
            <option value="lojas-desc"${app.ordem === "lojas-desc" ? " selected" : ""}>nº de lojas</option>
            <option value="nome-asc"${app.ordem === "nome-asc" ? " selected" : ""}>nome (A–Z)</option>
          </select>
        </label>
      </div>`;

    const destaque = `
      <div class="destaque-poupanca">
        <strong>Mais barato: ${dinheiro(melhor.preco)}</strong>
        <span class="poupanca-sub">${esc(melhor.nome)} · ${esc(nomeFonte(melhor.fonte))}${melhor.lojas > 1 ? ` · ${melhor.lojas} lojas` : ""}</span>
      </div>`;

    ui.resultados.innerHTML =
      cabecalho +
      destaque +
      app.visiveis.map((item, i) => cartao(item, i, item === melhor)).join("");
  }

  /* ---------- gaveta de ofertas ---------- */

  async function abrirGaveta(indice) {
    const item = app.visiveis[indice];
    if (!item) return;

    if (app.pedidoOfertas) app.pedidoOfertas.abort();
    const ctrl = new AbortController();
    app.pedidoOfertas = ctrl;

    app.focoAnterior = document.activeElement;
    ui.gavetaTitulo.textContent = item.nome;
    ui.gavetaCorpo.innerHTML = Array.from(
      { length: 4 },
      () => '<div class="esqueleto" style="height:52px;margin-bottom:.55rem"></div>'
    ).join("");

    ui.gavetaFundo.hidden = false;
    requestAnimationFrame(() => {
      ui.gavetaFundo.classList.add("visivel");
      ui.gaveta.classList.add("aberta");
      ui.gaveta.setAttribute("aria-hidden", "false");
    });
    document.body.classList.add("sem-scroll");
    ui.fechar.focus({ preventScroll: true });

    const url =
      "/api?acao=ofertas&fonte=" + encodeURIComponent(item.fonte) +
      "&url=" + encodeURIComponent(item.url || "") +
      "&preco=" + encodeURIComponent(item.preco) +
      "&nome=" + encodeURIComponent(item.nome);

    try {
      const resposta = await fetch(url, { signal: ctrl.signal });
      const dados = await resposta.json().catch(() => ({}));
      if (!resposta.ok) throw new Error(dados.erro || `Erro ${resposta.status}`);

      ui.gavetaCorpo.innerHTML = tabelaOfertas(dados, item);
    } catch (erro) {
      if (erro.name === "AbortError") return;
      ui.gavetaCorpo.innerHTML = `
        <div class="erro-gaveta">
          <p><strong>Não foi possível obter os preços por loja.</strong></p>
          <p>${esc(erro.message || "Erro desconhecido")}</p>
          ${
            item.url
              ? `<a class="acao primaria" href="${esc(item.url)}" target="_blank" rel="noopener noreferrer">Abrir na loja</a>`
              : ""
          }
        </div>`;
    }
  }

  function tabelaOfertas(dados, item) {
    const ofertas = dados.ofertas || [];

    if (!ofertas.length) {
      return `
        <div class="erro-gaveta">
          <p><strong>Sem ofertas listadas.</strong></p>
          <p>Esta loja não publica preços por loja para este artigo.</p>
          ${
            item.url
              ? `<a class="acao primaria" href="${esc(item.url)}" target="_blank" rel="noopener noreferrer">Abrir na loja</a>`
              : ""
          }
        </div>`;
    }

    const barato = ofertas[0];
    const caro = ofertas[ofertas.length - 1];
    const varias = ofertas.length > 1;
    const temUrls = ofertas.some((o) => o.url);

    const resumo = varias
      ? `<div class="destaque-poupanca">
           <strong>Poupas ${dinheiro(dados.poupanca)}</strong> no preço do artigo
           <span class="poupanca-sub">
             em <strong>${esc(barato.loja)}</strong> (${dinheiro(barato.preco)}) em vez de
             <strong>${esc(caro.loja)}</strong> (${dinheiro(caro.preco)}) ·
             ${ofertas.length} lojas comparadas
           </span>
         </div>`
      : `<div class="destaque-poupanca">
           <strong>${dinheiro(barato.preco)}</strong>
           <span class="poupanca-sub">
             na ${esc(barato.loja)}. Esta loja vende diretamente — não há outras ofertas para comparar.
           </span>
         </div>`;

    const linhas = ofertas
      .map(
        (o, i) => `
        <tr class="${i === 0 && varias ? "primeira" : ""}">
          <td class="loja-nome">
            ${esc(o.loja)}
            ${i === 0 && varias ? '<span class="etiqueta-mini">mais barato</span>' : ""}
          </td>
          <td class="preco-cel${i === 0 ? " melhor" : ""}">
            ${dinheiro(o.preco)}
            ${o.preco_antigo ? `<span class="riscado">${dinheiro(o.preco_antigo)}</span>` : ""}
          </td>
          <td>${o.envio ? esc(o.envio) : "—"}</td>
          <td>${dataCurta(o.atualizado)}</td>
          ${
            temUrls
              ? `<td>${
                  o.url
                    ? `<a class="ver-loja" href="${esc(o.url)}" target="_blank" rel="noopener noreferrer">Ver</a>`
                    : ""
                }</td>`
              : ""
          }
        </tr>`
      )
      .join("");

    return `
      ${resumo}
      <table class="tabela">
        <thead>
          <tr>
            <th>Loja</th>
            <th>Preço</th>
            <th>Envio</th>
            <th>Atualizado</th>
            ${temUrls ? "<th></th>" : ""}
          </tr>
        </thead>
        <tbody>${linhas}</tbody>
      </table>
      ${
        !temUrls && item.url
          ? `<div class="acao-fim">
               <a class="acao primaria" href="${esc(item.url)}" target="_blank" rel="noopener noreferrer">
                 Abrir página do produto
               </a>
             </div>`
          : ""
      }
      <p class="nota-gaveta">
        Preços recolhidos de páginas públicas. Confirma sempre o valor final no site da loja,
        sobretudo portes e stock.
      </p>`;
  }

  function fecharGaveta() {
    if (app.pedidoOfertas) {
      app.pedidoOfertas.abort();
      app.pedidoOfertas = null;
    }

    ui.gaveta.classList.remove("aberta");
    ui.gaveta.setAttribute("aria-hidden", "true");
    ui.gavetaFundo.classList.remove("visivel");
    document.body.classList.remove("sem-scroll");

    setTimeout(() => {
      ui.gavetaFundo.hidden = true;
      ui.gavetaCorpo.innerHTML = "";
    }, 320);

    if (app.focoAnterior && typeof app.focoAnterior.focus === "function") {
      app.focoAnterior.focus({ preventScroll: true });
    }
    app.focoAnterior = null;
  }

  /* ---------- eventos ---------- */

  function ligarEventos() {
    ui.form.addEventListener("submit", (evento) => {
      evento.preventDefault();
      pesquisar(ui.q.value);
    });

    ui.fontes.addEventListener("click", (evento) => {
      const botao = evento.target.closest("[data-chave]");
      if (botao) alternarFonte(botao.dataset.chave);
    });

    ui.sugestoes.addEventListener("click", (evento) => {
      const botao = evento.target.closest("[data-t]");
      if (!botao) return;
      ui.q.value = botao.dataset.t;
      pesquisar(botao.dataset.t);
    });

    ui.resultados.addEventListener("click", (evento) => {
      const botao = evento.target.closest("[data-ofertas]");
      if (botao) abrirGaveta(Number(botao.dataset.ofertas));
    });

    ui.resultados.addEventListener("change", (evento) => {
      if (evento.target.id === "ordem") {
        app.ordem = evento.target.value;
        desenharResultados();
      }
    });

    ui.fechar.addEventListener("click", fecharGaveta);
    ui.gavetaFundo.addEventListener("click", fecharGaveta);

    document.addEventListener("keydown", (evento) => {
      if (evento.key === "Escape" && ui.gaveta.classList.contains("aberta")) fecharGaveta();
    });
  }

  /* ---------- arranque ---------- */

  async function iniciar() {
    ligarEventos();

    let guardadas = null;
    try {
      const bruto = localStorage.getItem("comparador.fontes");
      if (bruto) guardadas = JSON.parse(bruto);
    } catch {
      /* ignora */
    }

    try {
      const resposta = await fetch("/api?acao=lojas");
      if (!resposta.ok) throw new Error(`HTTP ${resposta.status}`);
      const dados = await resposta.json();
      app.lojas = dados.lojas || [];

      const validas = new Set(app.lojas.map((l) => l.chave));
      const escolhidas = Array.isArray(guardadas) ? guardadas.filter((c) => validas.has(c)) : [];
      app.ativas = new Set(escolhidas.length ? escolhidas : validas);

      desenharFontes();
    } catch (erro) {
      desenharFontes();
      mostrarVazio(
        "O servidor não está a responder",
        "Recarrega a página. Se o problema continuar, tenta mais tarde."
      );
      console.error(erro);
    }
  }

  iniciar();
})();
