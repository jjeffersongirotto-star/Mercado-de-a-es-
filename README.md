# Screener B3

Filtro de ações da B3 com indicadores fundamentalistas (P/L, P/VP, DY, ROE, ROIC, margens, EV/EBITDA, dívida, VPA, LPA e outros).

![Screenshot](screenshot.png)

## Fontes de dados
- **Fundamentus** (principal): tabela geral com todas as ações em uma única requisição.
- **Status Invest** (complemento): preenche apenas o que o Fundamentus não tem.
- **brapi.dev** (opcional): nomes e setores das empresas.

Nenhuma das fontes exige token. Fundamentus e Status Invest não têm API oficial; os dados são lidos dos sites e podem mudar se os sites mudarem.

## Legenda
- **Vermelho**: divergência grosseira entre Fundamentus e Status Invest (passe o mouse para ver os dois valores).
- **Negrito**: valor vindo só do Status Invest.
- *Itálico*: VPA/LPA calculado (preço ÷ P/VP ou preço ÷ P/L).

## Filtros inteligentes
Os filtros funcionam em conjunto. Para indicadores em que "mais é melhor" (DY, ROE, ROIC, margens...) o valor digitado vale como **≥**; para "menos é melhor" (P/L, P/VP, EV/EBITDA, dívida...) vale como **≤**. Percentuais são digitados como número (8 = 8%).

## Rodar localmente
```bash
./run.sh
# abra http://localhost:8000
```
Ou manualmente:
```bash
pip install -r requirements.txt
uvicorn server:app --port 8000
```

## Publicar online
O app tem backend em Python, então **não roda no GitHub Pages**. Para ter um link público, conecte este repositório a um serviço como [Render](https://render.com) ou [Railway](https://railway.app):
- Build: `pip install -r requirements.txt`
- Start: `uvicorn server:app --host 0.0.0.0 --port $PORT`

Os dados ficam em cache e são atualizados a cada 30 minutos (ou pelo botão "Atualizar").
