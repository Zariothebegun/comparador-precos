import sys
import providers as p

TESTES = [
    ("continente", "leite"),
    ("auchan", "leite"),
    ("globaldata", "iphone"),
    ("kuantokusta", "iphone 17e"),
]

for chave, termo in TESTES:
    fornecedor = p.obter(chave)
    try:
        itens = fornecedor.pesquisar(termo)
        print(f"{fornecedor.nome}: {len(itens)} resultados para '{termo}'")
        for r in itens[:4]:
            print(f"   {r.preco:>8.2f} EUR | lojas={r.lojas:<3} | {r.nome[:60]}")
        if itens and itens[0].detalhe:
            ofertas = fornecedor.ofertas(itens[0])
            print(f"   -> {len(ofertas)} ofertas por loja para: {itens[0].nome[:50]}")
            for o in ofertas[:5]:
                print(f"      {o.preco:>8.2f} EUR | {o.loja[:32]}")
    except Exception as e:
        print(f"{fornecedor.nome}: ERRO {type(e).__name__}: {e}")
    print()
