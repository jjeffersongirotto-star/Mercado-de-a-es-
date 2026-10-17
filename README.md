# JG Investing

Filtro de ações da B3 (e de outros países, via TradingView) com indicadores fundamentalistas, consenso entre várias fontes,
grupos prontos, comparação, previsão de rentabilidade/aluguel e um chat sobre os dados do site.

![Screenshot](screenshot.png)

**Como usar o site, regras do consenso, cores, glossário e fontes de cada dado**: painel ⓘ do próprio site
(`#infoModal` no `index.html` — fonte única dessas explicações).
**Regras para alterar o código**: [`AGENTS.md`](AGENTS.md).

## Rodar localmente
```bash
./run.sh
# abra http://localhost:8000
```
Ou manualmente:
```bash
pip install -r requirements.txt
bash scripts/build_css.sh   # opcional: CSS pronto; sem ele o site usa o Tailwind do CDN
uvicorn server:app --port 8000
```

## Publicar (Render)
O app tem backend em Python, então **não roda no GitHub Pages**. No Render (serviço web):
- Build: `pip install -r requirements.txt && bash scripts/build_css.sh`
- Start: `uvicorn server:app --host 0.0.0.0 --port $PORT`
- Health check: `/api/status`

O site também é um **app instalável** (PWA): manifesto em `/manifest.webmanifest`, ícones em `static/icons/` e `sw.js`.
Como instalar no celular: painel ⓘ → **Como usar** → **Instalar o app**.

Variáveis de ambiente:

| Variável | Para quê |
|---|---|
| `GEMINI_API_KEY` | chat com IA (sem ela o chat responde só com as regras) |
| `GITHUB_TOKEN` | (opcional) token do GitHub com permissão de escrita no conteúdo do repositório: guarda o registro do chat em `data/chat_log.jsonl` na branch `data` (sem ele, o registro some a cada publicação) |
| `GEMINI_MODEL` | (opcional) modelo do Gemini usado primeiro |
| `YF_LIVE` | `1` liga a consulta ao vivo do Yahoo (no Render fica desligada: o Yahoo bloqueia IPs de nuvem) |
| `TW_CDN` | `1` volta ao Tailwind do CDN em vez do CSS gerado no build |
| `SNAPSHOT_RAW_BASE`, `APP_URL` | endereço da branch `data` e do site (padrões em `snapshots.py`) |

O deploy automático pelo GitHub não está chegando ao Render: depois do merge na `main`, publique pelo deploy hook ou pela API do Render.
`.github/workflows/keepalive.yml` acessa o site a cada 10 min para o plano gratuito não dormir.

## App Android (APK com widget)
`android/` gera o app JG Investing para Android (abre o site em tela cheia e traz o widget Favoritos e grupos — o chip do topo troca entre Favoritos e os grupos da aba Grupos; cada linha tem o logo da empresa (B3, ações de fora e BDRs; ação de fora com preço na moeda dela, da aba Ações do país; `scripts/build_logos.py`, semanal, na branch `data`; ajustes em `scripts/logos_override/`) e o nome curto; uso: painel ⓘ → **Instalar o app** → **App Android com widget**).
Nome, cor, endereço e ícone vêm do site no build (AGENTS.md, tabela 1.3). Para gerar o APK assinado (JDK 17 e Android SDK com a plataforma 36):
```bash
cd android && JG_SIGNING=/caminho/keystore.properties ./gradlew testReleaseUnitTest assembleRelease   # app/build/outputs/apk/release/app-release.apk
```
`keystore.properties` (storeFile, storePassword, keyAlias, keyPassword) e a chave ficam **fora do repositório**; use sempre a mesma chave
para a nova versão instalar por cima. Nova versão: suba `versionCode`/`versionName` em `android/app/build.gradle` e gere o APK:
o build copia o APK assinado para `static/app/JG-Investing.apk` (botão **Baixar APK**, rota `/app.apk`) e grava `static/app/version.json` (versão e SHA-256: o painel ⓘ mostra a versão e o app instalado oferece a atualização ao abrir ou voltar ao app, e o widget mostra **Atualização disponível**; confere o SHA-256 e abre o instalador); faça commit dos três.

## Como os dados chegam ao servidor
Os dados são atualizados a cada 30 minutos (ou pelo botão ⟳). Fontes que bloqueiam o servidor usam a cópia (snapshot) da branch **`data`**,
que não dispara deploy.

| Fonte | Como chega ao Render | Países |
|---|---|---|
| Fundamentus | ao vivo (se falhar: cópia diária da branch data, `fundamentus.json`) | BR |
| Status Invest | ao vivo → snapshot se bloquear (HTTP 403) | BR |
| TradingView (scanner) | ao vivo em lote → snapshot `tradingview_<país>.json` se bloquear | BR, EUA, Reino Unido, Alemanha, Portugal, Japão |
| Investidor10, Dados de Mercado, CVM (DFP/ITR) | snapshot diário | BR |
| Yahoo (yfinance) | snapshot diário (desempate de divergências) | BR |
| B3 (COTAHIST, proventos, índices, cadastro, aluguel, fluxo) | snapshots diários | BR |
| Yahoo (histórico das ações de fora) | snapshot `history5/` das maiores de cada país (renova 1×/semana, etapa `history`) + dias novos ao vivo; as demais só ao vivo | EUA, Reino Unido, Alemanha, Portugal, Japão |

Rotina diária (19:05): `scripts/push_snapshot_from_here.sh` atualiza os snapshots em sequência numa máquina cujo IP não é bloqueado
(`ONLY="cvm tradingview"` limita as etapas). No GitHub, `.github/workflows/data.yml` roda o mesmo script em dias úteis às 19:45
(todas as etapas menos Status Invest, que tem o workflow `.github/workflows/statusinvest.yml`, 19:30) e depois recarrega o site;
etapa bloqueada no runner mantém o snapshot anterior. A etapa `fg` calcula o Índice de Medo e Ganância da B3 (`scripts/build_fg.py`, histórico desde 1997). A etapa `modelos` (depois de `fg`) gera os sinais semanais dos modelos da Previsão (`scripts/build_modelos.py`, ~2 min). A etapa `kb` (base do chat: resumos da Wikipedia e personagens/elenco da Wikidata dos itens do
`conhecimento.json`) só baixa tudo de novo uma vez por semana; nos outros dias busca apenas os itens novos. Rodar à mão: Actions → Rotina diária de dados → Run workflow.
A fonte usada e a data de cada snapshot aparecem em `/api/status`.

## Chat
`chat.py` entende a pergunta sem IA quando consegue (tickers, nomes e apelidos, indicadores, setor, filtros, período, conversa anterior);
o que não entende vai ao Gemini, que interpreta a pergunta e os números saem dos dados do site. Explicações, passo a passo e glossário
vêm do painel ⓘ; os nomes de botões, da própria interface.
Personagens e atores (snapshot `kb`) também são reconhecidos; nome presente em mais de uma obra → o chat pergunta qual.
Assunto fora do mercado: quem é/o que é → empresa ligada (país, bolsa e índice) → sites especializados.
Sem a IA (fora do ar ou sem chave), responde com o `conhecimento.json` + resumos da Wikipedia (snapshot `kb`) e com uma busca
no painel ⓘ; gírias, sinônimos, apelidos e as variações de frases (para não repetir a mesma resposta) ficam em `vocabulario.json`.
Registro de perguntas: `/api/chat/log` (`?only=sem_resposta` ou `?only=reclamacao`, `&n=500`; apagado a cada reinício do servidor).

## Testes
```bash
python tests/test_consensus.py && python tests/test_chat.py && python tests/test_medo.py && python tests/test_modelos.py && python tests/test_history.py
for f in tests/*.js; do node "$f"; done
node tests/ui_smoke.cjs http://127.0.0.1:8000   # telas (precisa do Playwright e do servidor rodando)
```
Em cada PR o workflow `.github/workflows/ui-test.yml` roda tudo isso sozinho.
