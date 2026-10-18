# Diretrizes do projeto — JG Investing

Regras para quem altera este repositório (pessoas, Claude, Grok ou outro assistente). Leia antes de mudar qualquer coisa.
O `README.md` explica **o que o site faz e como rodar/publicar**; este arquivo explica **como mudar o código sem quebrar padrões**.
Nada aqui repete o README: quando precisar de um detalhe dele, aponte a seção.

Idioma: português do Brasil em textos da interface, mensagens de commit, comentários e documentação.

---

## 1. Regra principal: informação duplicada não é aceita

Toda informação existe em **um único lugar** (a fonte). Todo o resto — outras abas, o chat, o Gemini, scripts, testes — **lê da fonte**.
Alterou a fonte, tudo que depende dela muda junto. Uma mudança que copia informação já existente **não é aceita**: refaça lendo da fonte.

**Campos, botões e filtros podem se repetir** em outras abas quando a tela precisa deles (ex.: Valor inicial e Aporte mensal na Previsão e no Comparar → Modelos).
**Informação** (dados, regras, cálculos, textos de explicação, listas) pode **aparecer** em vários lugares, mas é **guardada só na fonte** e todos
leem dela — nunca escreva uma segunda cópia, para não existirem duas versões diferentes do mesmo assunto.

### 1.1 Antes de criar qualquer coisa
1. **Procure** se já existe (`grep` pelo nome, rótulo, valor ou texto). Existe → **use ou estenda**.
2. Precisa de uma variação → **parametrize** a função/classe existente; não copie e altere.
3. Dá para **calcular ou ler** a partir de outra informação → calcule/leia; não guarde uma segunda versão.
4. Achou uma duplicação antiga → **resolva na mesma mudança** (escolha a fonte, faça os outros lugares lerem dela, apague as cópias).

### 1.2 Um grupo de informação, uma fonte
Todos os itens de um mesmo grupo vêm **da mesma fonte**. Não se mistura fonte item a item:
- os dados de todas as empresas (nome, preço, indicadores) vêm de `/api/data` (`state.data.rows` no navegador). Nenhuma aba pega
  o Itaú de um lugar e a Petrobras de outro, nem "completa" o que falta de uma empresa com outra fonte;
- faltou o dado numa empresa → mostre "—" (sem dado), nunca o valor de outra fonte só para ela;
- se uma fonte não existe para um contexto inteiro (ex.: não há B3 fora do Brasil), o contexto **todo** usa a outra fonte
  (Brasil = B3; exterior = TradingView) — escolha por país/contexto, nunca por empresa;
- quando uma informação precisa de outra fonte para todos os itens, mude a fonte do grupo inteiro (e documente na tabela 1.3).
- o seletor de fonte do topo vale para todos os cards: escolhida uma fonte, todo valor exibido é o dela ("—" se ela não tiver);
  "Todos" mostra o consenso (ou a fonte com prioridade, como a B3, onde a tabela 1.3 indicar).
- "não duplicar" é sobre o site, não sobre as fontes: os dados são carregados uma vez e toda aba reaproveita a mesma cópia e as mesmas
  funções (ex.: o card de uma ação é montado por `blockHtml`/`cardsHtml` em Ações e em Grupos).

### 1.3 Onde cada informação mora

| Informação | Fonte única | Quem lê dela |
|---|---|---|
| Dados das empresas (nome, setor, preço, variação, indicadores de consenso) | `/api/data` → `rows` (montado em `server.build`/`finalize`) | todas as abas (`state.data.rows`), CSV, chat e Gemini (`chat.build`) |
| Tabela do Fundamentus (endereço e leitura) | `fundamentus.py` (`URL`, `parse`); ao vivo e, se falhar, a cópia diária da branch `data` (`fundamentus.json`, `scripts/fetch_fundamentus.py`) | `server.fetch_fundamentus`, `indicadores_fundamentus.py`, `scripts/snaputil.py` |
| Indicadores (chave, rótulo, unidade, direção, colunas das fontes, limiar) | `server.py` → `FIELDS` | `/api/data` → `fields` → filtros, cards, ordenação, CSV; chat |
| Fontes de dados (id, nome, logo, países) | `server.py` → `SOURCES` | seletor de fonte, contagens, status |
| Países e moedas | `tradingview.py` → `COUNTRIES` | `/api/countries`, seletor de país |
| Regras de consenso entre fontes | `consensus.py` | cores/selos dos cards (`st`, `cm`, `ag` de cada linha) |
| Histórico, proventos e métricas por período (valorização 1–5 anos, DY médio, proventos do ano, 1º pregão) | snapshot `metrics` (`/api/metrics`, gerado por `scripts/build_metrics.py` a partir da B3) | Grupos, rankings do chat |
| Volume financeiro por período (dia, 10 pregões, 1–12 meses) | Brasil em "Todos": snapshot `metrics` → `vol` (B3, `scripts/build_metrics.py`; prioridade B3) · fonte escolhida: o valor dela (`S`) · exterior: TradingView | filtro Volume (grupo `vol`), cards, Só líquidas (`liq2m`), Grupos, chat |
| Crescimento de receita e lucro (1–5 anos) | 5 anos: consenso das fontes · 1–4 anos: só CVM (`scripts/build_cvm.py` → `cresc{n}a`, `lucro{n}a`) · exterior: TradingView (só 5 anos) | filtro Crescimento (grupo `cres`), cards, Grupos, chat |
| Campos com Período e posição em Ordenar | `server.py` → `FIELD_EXTRA` (`grp`, `per`, `sub`, `sort`) | filtros, cards e Ordenar (`app.js`) |
| Universo exibido (ilíquidas, 1 ticker por empresa) | `scripts/universe.py` (`mark` grava `il` e `k1` em cada linha de `/api/data`) | site (`tradable`, `universe` em `app.js`), Grupos, `/api/returns`, scripts de snapshot |
| Nomes dos índices (Ibovespa, Dólar, CDB, IPCA, Poupança, Ouro) | `history.py` → `INDICES` (o site recebe em `window.INDICES`) | gráficos (`grafico.js`), Comparar, chat (`IDXN`) |
| Histórico de preços e proventos das ações de fora (maiores de cada país: `history.FORA`; mensal desde o início, diário 10 anos) | branch `data` → `history5/` (`scripts/fetch_history.py` → `history.copy_update`, renova 1×/semana) + dias novos do Yahoo (`history.yget`) | gráficos e Comparar de ações estrangeiras |
| Índice de cada país e símbolo no Yahoo | `tradingview.py` → `YAHOO` | `/api/countries` (`index`), gráficos e Comparar de ações estrangeiras, chat (empresa ligada) |
| Bolsa principal de cada país (B3, NYSE/Nasdaq, Bolsa de Tóquio…) | `tradingview.py` → `BOLSA` | chat (empresa ligada: "país · bolsa · índice") |
| Registro de erros | `server.py` → `ERRS` (`/api/errors`) e log do Render | quem mantém o site |
| Variação de preço entre duas datas escolhidas | `server.period_returns` | aba Comparar (`/api/returns`), perguntas do chat com período |
| Data de listagem | Brasil: `metrics.ftd` (1º pregão na B3) · exterior: `ipo` (TradingView) | Novidades e etiqueta NOVA (`grupos.js` → `listDate`) |
| Explicações ao usuário: regras, cores, **passo a passo** de cada aba, **glossário** | painel ⓘ — `#infoModal` em `index.html` | usuário; chat e Gemini (`chat.guide`, `guide_sections`, `glossary`); botão ⓘ dos indicadores (`glossOf`, termo em `FIELD_EXTRA` → `gl`) |
| Nomes de botões, abas, campos e opções | a própria interface (`index.html` e `*.js`) | chat e Gemini (`chat.ui_labels()` lê da interface) |
| Significado de cada cor | seção **Cores** do painel ⓘ | usuário; chat |
| Paleta, alturas, raios, sombras | `index.html` → bloco `/* Design system */` (`:root { --c-pos … }`) | todo CSS (`var(--…)`) |
| Contexto para a IA do chat (pessoas, futebol, filmes, séries, animes, jogos, estúdios, o que fazem as empresas, temas → setores) | `conhecimento.json` (data em `atualizado`; grupos em `chat.KB_CATS`) | `chat.kb_context` → Gemini (só os itens citados na pergunta); `chat.kb_answer` sem IA; lista de itens do snapshot `kb` |
| Resumos da Wikipedia, outros nomes, personagens e elenco dos itens do `conhecimento.json` | snapshot `kb` (`scripts/build_kb.py`: Wikipedia + Wikidata; rotina diária, renova 1×/semana) | `chat.wiki` → índice de nomes (`chat._names`), `kb_context`, `kb_answer`, "Está falando de qual?" (`kb_ambiguous`), busca (`chat.search`) |
| Vocabulário do chat: sinônimos e gírias → indicador, qualificadores (barato, pouca dívida, boa pagadora, queda), abreviações, apelidos de empresas, palavras → termo do Glossário, variações de frases, nomes que não viram personagem | `vocabulario.json` | `chat.py` (`SYN`, `QUALS`, `ABBR`, `ALIAS`, `GLOSS_SYN`, `frase`) |
| Barato/Caro, só empresas brasileiras (ação de fora e BDR: "Sem valor justo" · "Empresa estrangeira", `FAIR.so_br`/`bdr_re`, `valor_justo.estrangeira`) (valor justo: Graham; Gordon em bancos e seguradoras; P/VP do setor em holdings e imobiliárias; Barsi em elétricas, saneamento, gás e rodovias pelo segmento da B3) | `valor_justo.py` → `FAIR` (margem que arredonda para 0% = 0 `zero`, `margem`; custo de capital, crescimento, subsetores, mínimo de empresas, teto do lucro, janelas do LPA `lpa_anos`, taxa/anos/segmentos do Barsi, textos sem valor justo `rot`) e `fair`, `lpa_ref` (média de 3 anos; prejuízo nela → 5 anos; sem média → 12 meses), `rotulo` (Prejuízo recorrente / Sem valor justo); `server.lucro_pl` → `ln3`, `ln5`, `roe3`; `valor_justo.dps_medio` → `dpsm`; segmento B3 → `seg` (`server.finalize`, cadastro `b3_cad`); o site faz a mesma conta em `app.js` → `fairOf`/`lpaRef` (configuração em `/api/data` → `fair`, respeita o seletor de fonte) | card (Mercado e Grupos), grupo Baratas pelo Graham (`grupos.js`), chat (`chat.fair`), widget do app Android (`/api/widget`) |
| Ticker ↔ CNPJ da companhia (Brasil) | CVM, cadastro FCA (`scripts/build_cvm.py` → `tickers`: entregas dos últimos 5 anos, a mais recente de cada empresa; outras classes da mesma raiz quando ela tem um só CNPJ; só papéis da lista B3 `b3_listed`) | `cvm.json`, `fund.json` (`scripts/build_fund.py`) |
| EBIT, EBITDA (EBIT + depreciação/amortização da DFC), dívida líquida, Dív. líq./EBITDA, payout (dividendos + JCP declarados na DMPL ÷ lucro do último exercício), lucro anual desde 2009 | CVM DFP/ITR (`scripts/build_cvm.py` → `_ebitda`, `dlebitda`, `payout`; `scripts/build_fund.py` → `fund.json`) | Barato/Caro (`server.build` → `al`), alertas ⚠️, chat |
| Dividendo por ação de cada ano (5 anos completos, ajustado por desdobramento/grupamento/bonificação) | B3, proventos em dinheiro (`scripts/fetch_b3_proventos.py` → snapshot `b3_proventos`, rotina, renova 1×/semana) | Barato/Caro → Barsi (`dpsm`). Pendente: `metrics` (DY médio dos Grupos) ainda usa o histórico do Yahoo antes dos últimos 12 meses |
| Alertas ⚠️ do Barato/Caro (Dív. líq./EBITDA, DY, payout) | `valor_justo.py` → `FAIR` (`al_*`) e `alertas`; o site faz a mesma regra em `app.js` → `alertsOf`; explicação no Glossário (**Alertas (⚠️)**) | card (Mercado e Grupos), chat (`chat.fair_answer`) |
| Índice de Medo e Ganância da B3 (0–100, diário desde 1997; faixas e partes) | snapshot `fg` (`scripts/build_fg.py`: COTAHIST, fluxo B3, CDI; rotina diária) → `/api/fg` | velocímetro (`medo.js` → `fgLoad`, `fgBand`), Comparar, chat (`chat.fg_answer`) |
| Modelos da Previsão (regras, custos, IR, grupos prontos do rodízio, referências CDB e Ouro, pontos das Colocações, setores perenes e teto do Método Barsi) | `modelos.py` → `MODELOS`, `REF`, `GRUPOS`, `HIB`, `PONTOS`, `PERENE_RX`/`PERENE_TXT` (+ segmento do cadastro `b3_cad`), `BARSI_*` (híbrido; explicação no painel ⓘ → **Modelos da Previsão**) | `/api/modelos` → card Modelos, abas Tabela/Desempenho (`previsao.js`); `/api/modelos/comparar` (`modelos.compare`, `ranking`, `top_sector`) → Comparar → Modelos (`comparar.js` → `modRun`, `modHtml`); chat |
| Sinais semanais dos modelos (índice da ação, média de 200 dias, alta em 12 meses, chance do algoritmo 1 e 3 meses, lucro no último balanço publicado) | snapshot `modelos` (`scripts/build_modelos.py`; lucro de `fund.json` ← `scripts/build_fund.py`, DFP da CVM; "mercado" de `build_fg.market`, índice da ação de `medo.stock_index`; CDB de `history.bcb`) | `modelos.py` |
| Ações inteiras, JCP líquido e movimentações uma a uma (todos os modelos) | `modelos.py` → `Conta.buy/sell/raise_cash` (piso/teto em ações inteiras; a sobra fica no caixa da faixa, no CDB) e `grupo` (reserva `pend` por empresa rendendo CDB, volta ao caixa quando a empresa sai do alvo); JCP: `scripts/build_modelos.py` grava `jc` (JCP por ação na semana) e `tp` (tipos J/D/R/K da lista da B3) no snapshot `modelos` → `build` monta `JT` (15% retido, `JCP_IR`) e `DV` líquido, `DT` (tipos); movimentações: lista de eventos `{d, k: compra/venda/aporte/provento/cdi_ap/cdi_res/retirada/imposto, t, q, p, v, x, pct}` em `rotate` e `grupo(rec=True)` (CDI = uma linha por semana com a variação do saldo no CDB sem o rendimento, `_cdi`; até `MOV_MAX` mais recentes + aporte inicial, `_ult`) | `previsao.js` → `movHtml`/`movRow` (Data · Movimentação · Qtd. de ações · Valor, "Mostrar mais" de 60 em 60), usado em `groupHtml` e `simHtml`; ⓘ **Modelos da Previsão** (chat lê) |
| Modo Grupo do Comparar (uma carteira por modelo; Média da carteira) | `modelos.py` → `grupo`, `_gtargets`, `GRUPO_K`; `modelos.compare` → `cart` (calculado no servidor, cache do Comparar) | Comparar → Modelos (`comparar.js` → `modGrupo`, coluna Média da carteira em `modTables`); Previsão (Média); explicação no ⓘ **Modo Grupo** (chat lê) |
| Grupo simulação (aba Grupos: uma carteira por modelo desde a data inicial, mesmo valor inicial, até a última semana dos dados) | `modelos.py` → `simgrupo` (usa o mesmo `grupo(..., rec=True)` do Modo Grupo, que também devolve movimentações e posição; nenhuma regra de modelo duplicada) → `POST /api/modelos/simgrupo` {di, v0} (cache `_C` por versão dos dados). Decisão: servidor, recalculado do início a cada versão dos dados (~0,3 s; preços antigos são ajustados por proventos/desdobramentos, então guardar posições e continuar poderia divergir); o site guarda o resultado no aparelho (`screenerB3.simgrupo.v2`; sobe a versão quando a conta muda — junto com `modelos.ENGINE` na chave do `_C` e `PRE_VER` do pré-cálculo) e pede 1×/dia. Grupo = `{name, tickers: [], sim: {di, v0}}` em `screenerB3.grupos.v1` (exportar/importar levam `sim`; fora do rodízio `userGroups`) | Previsão (`previsao.js` → `askSim`: Todos + Data inicial + Data final vazia = **Hoje (em andamento)**, opção no topo do calendário (`data-empty` do campo → `uiCalendar({empty})` devolve `` `''` ``) → `uiConfirm`; nome repetido → `uiChoose` Substituir / "Grupo simulação 2"; `gSim` de `grupos.js`); Grupos (`grupos.js` → `simBody`, toque no modelo → `pvGroupHtml` = `groupHtml`/`simHtml` da Previsão); ⓘ **Grupo simulação** (chat lê) |
| Período dos modelos (Previsão: chips 5…30 anos / Todo período + chip temporário das datas) | `previsao.js` → `PER`, `perDi`, `perC`/`perCOn` (chip "MM/AAAA a hoje" quando a Data inicial é posterior à mais antiga ou há Data final; `st.mperC` marca o chip; `modBody` usa exatamente `st.di`..`st.df`/fim), `perHtml` | ⓘ **Período** (chat lê) |
| Rend. médio anual (Previsão → Desempenho) | `modelos.py` → `anual` (blocos de 12 meses, Dietz modificado, média simples) chamado em `simulate`, `simulate_ref`, `rotate`; campo `ra` em `run` e `compare` | `previsao.js` → `drawDes`, `desHtml`, `refRows`; explicação no ⓘ **Rend. médio anual** (chat lê) |
| Comparar → Modelos pré-calculado (Todas e 5 maiores de cada setor × 5/10/15/20 anos e todo o período, valores padrão) | snapshot `modelos_pre` (`scripts/build_modelos_pre.py`, rotina, logo após `modelos`; mesma conta `modelos.compare`) | `server._pre` → `modelos.set_pre`; `modelos.compare` devolve a resposta pronta só se a chave `pre_key` bater (sinais, CDB, ouro, empresas, setores perenes, período, aportes); senão calcula ao vivo e guarda no cache |
| Medo e Ganância de cada ação hoje (card da aba Mercado, só no computador) | snapshot `fg_acoes` (`scripts/build_fg.py` → `acoes`, regra `medo.stock_index`, rotina) | `server.finalize` → `rows.fg` e `fga` (faixas) → `app.js` → `fgaHtml` |
| Notícias (aba Notícias: título, fonte, data, resumo curto, link e imagem de capa og:image) | snapshot `noticias` na branch `data` (`scripts/fetch_noticias.py`, rotina, bloco rápido; RSS do Bing Notícias + og:image/og:description da própria página; itens já publicados ficam) | `/api/noticias` → aba Notícias (`noticias.js`; imagem com carregamento preguiçoso, some se não abrir) |
| Aporte e retirada de cada mês da Previsão | `previsao.js` → `flows` | tabela da Previsão e simulação dos modelos |
| Comparar → Medo e Ganância de uma ação (índice da ação: `medo.stock_index`, mesma nota 0–100 de `medo.rank` usada pelo índice do mercado; altas/quedas semanais, demais mensais) | `medo.py` → `analyze` (histórico diário completo `history.b3full`, snapshot `fg`, Ibovespa) → `/api/fgcmp` | aba Comparar (`comparar.js` → `fgRun`, `fgHtml`) |
| Métodos de investimento (Barsi, Bazin, Graham, Buffett, Fórmula Mágica…) | painel ⓘ → seção **Métodos de investimento** | usuário; chat (`chat.method`, critérios em `METHODS`) |
| Carteira (compras e vendas) | `localStorage` `screenerB3.carteira.v2` no aparelho (`carteira.js`); posição, preço médio e proventos calculados do histórico | aba Carteira, Exportar/Importar |
| Utilitários do navegador: `esc`, `nf`, `F0`, `F2`, `pc`, `brl`, `norm`, `dataBR`, `parseBR`, `avgLastMonths`, `getRetry`, `fileIc`, `saveJSON` (Exportar) | `ui.js` (topo) | todos os scripts |
| Diálogos, toast, carregamento, Reorganizar (arrastar ⠿), calendário | `ui.js` → `uiConfirm`, `uiAlert`, `uiPrompt`, `uiChoose`, `uiToast`, `uiReorder`, `loaderHTML`, `uiCalendar` (todo `input type=date/month` vira `uiDateField` sozinho) | todas as abas |
| Formatação de indicadores (`fmt`, `fmtPrice`, `fmtBig`, `fmtMoneyBig`) e preço exibido (`priceOf`) | `app.js` | aba Mercado, Comparar, Carteira |
| Rendimento dos índices entre duas datas (Ibovespa, CDB…) | `server._idx_returns` | Comparar e chat (`/api/returns`), Carteira (`/api/idxret`) |
| Lista de scripts JS | tags `<script src="/static/…">` do `index.html` | servidor (`JS_FILES` é lido delas) |
| Versão (`?v=`) de JS/CSS | **automática** (hash do conteúdo, `server._index_html`) | não edite `?v=` à mão |
| Configuração do Tailwind | `tailwind.config.js` | build do CSS e, sem ele, o CDN no navegador |
| App instalável: nome e cor | `<title>` e `<meta name="theme-color">` do `index.html` | manifesto (`/manifest.webmanifest`, gerado pelo servidor) |
| App instalável: desenho do ícone ("JG Investing") | `scripts/icon-source.jpg` (quadrada) e `scripts/icon-source-round.jpg` (redonda, Android); `scripts/build_icons.py` gera `static/icons/` — não edite os PNG à mão | manifesto, tela inicial do celular |
| Marca comprida do topo do widget do app ("JG Investing" + gráfico) | `scripts/build_icons.py` → `marca_widget` e `WIDGET_PARTES` (da faixa `brand-source.jpg`) geram `static/brand/jg-investing-widget.png` (compacta) e `-nome`/`-graf` — não edite à mão | `android/app/build.gradle` → `ic_brand`, `ic_brand_nome`, `ic_brand_graf`; `FavWidget.render`: nome curto = marca esticada até o seletor colado ao horário (`brandBitmap`, `WidgetData.brandRoom`/`brandGrafPx`), nome longo = logo quadrado com o seletor no meio (`WidgetData.longLogo`) |
| Marca no topo do site (faixa "JG Investing") | `scripts/brand-source.jpg` (celular) e `scripts/brand-source-wide.jpg` (computador); `scripts/build_icons.py` gera `static/brand/` | cabeçalho do `index.html` (igual em todas as abas) |
| App Android (`android/`: site em WebView + widget Favoritos e grupos) | nome, cor, endereço e ícone lidos no build (`android/app/build.gradle`) de `index.html` (`<title>`, `theme-color`, cores do design system), `snapshots.py` (`APP_URL`) e `static/icons/`; lista dos Favoritos → app pela ponte `window.JGApp` (`app.js` → `pushApp`); grupos do seletor do widget = os da aba Grupos, com as mesmas ações (`grupos.js` → `groupData` → `pushGroups` → `JGApp.setGroups`; o servidor não recalcula grupos); dados do widget em `/api/widget` (`server.api_widget`: preço e variação de `/api/data`, Barato/Caro de `valor_justo.fair` (sem valor: `x` = texto curto de `valor_justo.rotulo`; o app até 1.6 ignora e mostra "—"), Medo e Ganância da ação de `rows.fg` ← snapshot `fg_acoes`; ação de fora: preço, variação e moeda da aba Mercado do país = TradingView (`server.foreign_quotes`: cópia de `cache.foreign` ou `load_tv`, renovada em segundo plano; snapshot `tradingview_<país>` enquanto ninguém pede), Barato/Caro de `valor_justo.fair` com LPA/VPA do TradingView, Medo e Ganância "—"; ticker = `WidgetData.TICKER` / `server.WIDGET_TK`, letras, dígitos, ponto e hífen) e gráfico de 5 anos em `/api/widget/chart` (`history.get` diário (de fora: `history.yget`, o mesmo de `chart_foreign`), o mesmo do gráfico do card, ~120 pontos; base = convenção de `grafico.js` → `pricePts`; cor da linha lida de `grafico.js`); toque numa ação → `?acao=` / `jgOpen` (`app.js`; ação de outro país: troca o país pela resposta `k` de `/api/widget`) | widget da tela inicial; Exportar dentro do app (`ui.js` → `saveFile`) |
| APK para baixar, versão publicada e SHA-256 | `versionCode`/`versionName` de `android/app/build.gradle` → build (tarefa `publishApk`) grava `static/app/JG-Investing.apk` e `static/app/version.json` (versionCode, versionName, apk, sha256) | botão Baixar APK do painel ⓘ (`/app.apk`, versão por `server.apk_version`); oferta de atualização dentro do app (`/app/version.json` → `Updater`, regras em `UpdateLogic`: 1.14+ confere SEMPRE ao abrir e ao voltar ao app (`openCheck`, só junta aberturas a menos de `OPEN_GAP` = 15 s); 1.15+ também a cada atualização de dados — seta/atualização automática do site (`app.js` → `JGApp.dataRefreshed` → `Updater.dataCheckAsync`) e ⟳/atualização dos widgets (`Updater.quietCheck`) — com a regra `UpdateLogic.dataCheck` (só `OPEN_GAP`) e o diálogo na tela se o app estiver aberto (`Updater.live`); em 1.14 o `FavWidget.render` sem proteção na thread do onResume podia matar a conferência antes do diálogo e deixar `checking` preso, sem cache (`url` com `?t=`, `no-store`), "Depois" só na memória por `SNOOZE` = 10 min; versão nova = `versionCode` maior, ou o mesmo com `versionName` maior por número (`cmpName`/`newer`; nunca comparar nomes como texto: "1.10" < "1.9"); até a 1.13 a trava de 10 min contava as conferências do widget e "Depois" valia 24 h → oferta sumia); aviso Atualização disponível no topo do widget (`FavWidget` → `Updater.quietCheck`, no máximo a cada 10 min). Formato do version.json não muda (a 1.2 o lê); o servidor acrescenta `dl` (`APK_MIRROR`, o mesmo APK no GitHub) para o site dentro do app até a 1.13 oferecer baixar pelo navegador (`ui.js` → user agent `JGInvestingApp/x` + `verCmp`, mesma regra de `cmpName`) |
| Entradas do Grupo simulação (valor inicial, aporte mensal, aportes e retiradas extraordinários) | `previsao.js` → `askSim` grava em `grupos.v1` `sim = {di, v0, ap, ex, ret}` (`simRows`: só as linhas confirmadas); Data final já em Hoje + Todos: tocar no campo → `uiConfirm` "Deseja criar grupo de simulação?" (Sim = cria; Não = abre o calendário do site (`ui.js` → `uiDateField` → `_udBefore`)); grupos antigos (só di/v0) seguem como estavam | `modelos.sim_def` (valida) → `modelos.sim_flows` (MESMA regra de `previsao.js` → `flows`/`apAt`/`wAt`: mês com retirada não aporta; mensal vale até a próxima, 0 encerra) → `simgrupo`/`simmov` (chave do cache com os fluxos; `grupo(..., wd=)`: retirada = caixa → reservas → venda proporcional de ações inteiras); `apT` = Σaportes − Σretiradas (valor aportado; % sobre ele) → Grupos (`simBody`, tile Aportado), widget (`/api/widget/simgrupo?f=` JSON {ap, ex, ret}, app 1.17+, coluna Valor aportado = `apT`) |
| Movimentações e posições do Grupo simulação (colunas Data · Tipo · Origem/destino · Valor ação · Qtd. de ações · Valor; preço médio) | `modelos.grupo` (rec: eventos com `p` = preço da ação na hora, também no provento, e `q`; posição `pm` = total pago com custos ÷ ações — vendas são totais e não mudam; `dv`/`dvt` = proventos líquidos por empresa); `modelos.simgrupo` manda só as `MOV_SITE` = 50 mais recentes e TODAS as posições; o resto vem de `/api/modelos/simmov` (`server.api_modelos_simmov` → `modelos.simmov`: páginas `off`/`n` ou só uma empresa `tk` com posição e proventos; guardado comprimido em `_MZ`, `MZ_MAX` = 12; se saiu, refaz só o modelo) | `previsao.js` → `movRow`/`movHtml` (50 por vez, "Mostrando N de M"; rodízio continua com as 400 mais recentes de `_ult`), `simHtml` (toque na empresa → `simCoHtml` embaixo; 2º toque fecha), `pvSimCompany` (janela só da empresa: `grupos.js` → `jgOpenSim(gn, m, 0, tk)` / `?sim=&m=&tk=`, widget 1.16+) |
| Widget Grupo simulação (app 1.15+) | grupos de simulação = os da aba Grupos (`grupos.js` → `pushSims` → `JGApp.setSims` [{id, n, di, v0}], dentro de `pushGroups`); dados em `/api/widget/simgrupo?di=&v0=` (`server.api_widget_simgrupo`: o mesmo `modelos.simgrupo` e cache da aba Grupos, posições `pa` [ticker, ações, investido, preço] — tiradas do POST da aba —, valor atual = caixa + ações × preço de agora de `/api/data`, variação do dia pelo `var`, todas as posições com nome popular) | `SimWidget`/`SimWidgetService`/`SimData` (1.16: títulos centralizados em 2 linhas `sim_col_*`, Modelo · Carteira (`np`) · Valor aportado · Valor atual · Variação do dia; marca comprida até o seletor como no Favoritos (`FavWidget.brandBitmap`, `WidgetData.longLogo`); lista plana `SimData.items`: toque no modelo abre título + TODAS as empresas + caixa no CDB, rolando; toque numa empresa → `WidgetTap` "sp" → janela da empresa no app; ↗ Abrir → `?sim=&m=` / `jgOpenSim` → mesmo modal de movimentações de `grupos.js` → `simModal`); seletor `PickerActivity` (`EXTRA_SIM`) |
| ⟳ do widget (1.13+) e horário mostrado | `server.api_refresh` com `src=widget` (o mesmo POST `/api/refresh` do ⟳ do site, uma atualização por vez; só refaz se `widget_should_refresh`: dados com mais de `WIDGET_STALE` = 10 min E `pregao()` seg–sex 10:00–18:30 Brasília; não limpa as ações de fora) | `RefreshJob` (espera `/api/status` até 120 s, depois `/api/widget`); horário do widget = quando os dados chegaram (`Store.fetchedAt`, `WidgetData.fetched`), não o `u` |
| Nome popular e aliases da empresa (widget, busca do site, chat) | `nomes_populares.json` (chave = 4 letras da raiz B3/BDR; EUA = ticker sem prefixo (`us:X` desfaz colisão com raiz da B3); outros países com prefixo `gb:`/`de:`/`pt:`/`jp:` (o mesmo ticker em outra bolsa é outra empresa); valor = nome ou `{n, aliases}`; ex.: PETR → Petrobras, GOOG → Google, META → Meta + facebook/instagram/whatsapp) → `snapshots.nome_popular` / `nome_busca` (sem entrada: `snapshots.nome_curto`); o nome oficial não muda | `/api/widget` → `s` (B3, de fora e BDR); `/api/data` → linhas com `pn` (`server.finalize`) → `app.js` `prepRow` (`r._s`) e `searchRank` (nível do nome); apelidos do chat (`chat.py`, menos `POP_SKIP`); widget (1.12+: linhas inteiras na altura do widget — `WidgetData.rows`/`headerDp`/`rowBaseDp`, títulos `w_cols` com altura fixa; 1.11+): nome em cima, em negrito (tamanho `WidgetData.nameSp`, 2 linhas se não couber), ticker embaixo em cinza |
| Abas do site (rótulo e ícone) | `index.html` (`nav.tabs`: `data-tab` interno inalterado — `acoes` é a aba **Mercado**; ícone SVG inline em `.ti`, rótulo em `.tl`; ativa = pílula cinza) | site e app (WebView); textos, ⓘ e conhecimento do chat (`chat.HOWTO_KEYS`, `chat.ui_labels`) usam os rótulos |
| Logo da empresa (widget do app) | `scripts/build_logos.py` (semanal, etapa `logos` da rotina): favicon do site oficial (CVM FCA `Pagina_Web`, serviço de favicons do Google) → ícone do próprio site (apple-touch-icon / rel=icon; também quando o favicon é menor que 64 px: fica o maior, se for mais nítido e o mesmo logo — `better`/`same_logo`/`sharpness`; ícone repetido em 3+ empresas = plataforma de RI, fora) → brapi (quadrado arredondado; sem o genérico) → outra classe da mesma empresa → iniciais. Ações de fora (EUA, Reino Unido, Alemanha, Portugal, Japão: os tickers de `tradingview_<país>`) e BDRs: site da empresa no Yahoo (`website`, até 600 por execução) ou Wikidata (P856), guardado em `data/logos/sites.json` (90 dias) → favicon → ícone do site → quadrado do TradingView (`s3-symbol-logo`, por `logoid`) → outra classe (GOOGL/BRK.B); BDR = logo da empresa de fora com o mesmo `logoid`; logo de fora transparente e quase todo escuro ganha fundo claro sozinho; ajustes à mão em `scripts/logos_override/` (chave = raiz B3 ou domínio) (imagem própria, fundo claro p/ logo escuro, etapas a pular, ícones genéricos) → branch `data` → `data/logos/index.json` + PNG 128×128 com nome = hash (o widget mostra até 96 px) | `/api/logos` e `/logos/<arquivo>` (`server.logo_index`, `logo_file`: em memória, cache 30 dias); `/api/widget` → `l` (arquivo; também para ticker de fora/BDR, que vem só com o logo) e `s` (nome popular: `snapshots.nome_popular`, fallback `nome_curto`); widget guarda os PNG no aparelho (`Logos`) |
| Nome do site/app ("JG Investing") | `index.html` → `<title>` (parte antes de " — ") | manifesto (`server.manifest`), chat e Gemini (`chat.site_name`) |
| Instalar por plataforma (Android = APK `/app.apk`; iPhone e computador = navegador; dentro do app nada) | `ui.js` (bloqueia o `beforeinstallprompt` no Android; classe `in-app` esconde `.no-app`) e painel ⓘ → **Instalar o app** | usuário; chat |
| App instalável: modo sem internet | `sw.js` (registrado no fim do `ui.js`) | celular |
| Endereços (branch `data`, site no Render), `br_num`, `when_sp` | `snapshots.py` (`RAW`, `APP_URL`) | servidor, `history.py`, `tiebreak.py`, `scripts/`, workflow `keepalive.yml` |
| Dados de snapshots | `snapshots.load(nome)` | nunca baixe a mesma URL por conta própria |

Informação nova sem lugar nesta tabela → escolha a fonte, acrescente a linha aqui e faça os demais lerem dela.

### 1.4 Chat e Gemini
O chat e o Gemini **não têm conteúdo próprio**: respondem com `/api/data`, `metrics`, `period_returns`, o painel ⓘ e os nomes da interface.
Para o chat explicar algo novo, escreva no painel ⓘ (o usuário também passa a ver). Texto longo demais para o usuário: deixe no ⓘ só o resumo e guarde o detalhe no mesmo item em `<span class="chat-only" hidden>` (o chat lê; a tela e o ⓘ do card não mostram). O vocabulário (sinônimos, gírias,
apelidos, frases) fica no `vocabulario.json`; em `chat.py` só fica o roteamento (palavras → indicador/filtro/seção do painel); `tests/test_chat.py` falha se uma seção citada não existir no painel.

---

## 2. Mapa do código

| Arquivo | Responsabilidade |
|---|---|
| `medo.py` | análise Comparar → Medo e Ganância (`analyze`, testada em `tests/test_medo.py`) |
| `modelos.py` | modelos da Previsão: regras e simulação semanal com custos, IR e CDB, rodízio em grupos (testado em `tests/test_modelos.py`) |
| `server.py` | API FastAPI, montagem dos dados (`build`, `finalize`), cache, rotas, servir HTML/JS/CSS |
| `consensus.py` | consenso entre fontes (testado em `tests/test_consensus.py`) |
| `chat.py` | chat: entendimento sem IA (`parse`), respostas com dados (`execute`), Gemini (`interpret`, `gemini2`, `ground`) |
| `snapshots.py` | snapshots da branch `data`, endereços e utilitários comuns ao servidor e aos scripts |
| `history.py`, `statusinvest.py`, `tradingview.py`, `tiebreak.py` | histórico de preços, coleta de cada fonte, desempate Yahoo |
| `index.html` | estrutura de todas as abas, CSS próprio (design system) e painel ⓘ |
| `ui.js` | utilitários e componentes compartilhados (carregado antes dos outros scripts) |
| `app.js` | aba Mercado, estado global (`state`) e formatação de indicadores |
| `grupos.js`, `carteira.js`, `medo.js`, `comparar.js`, `previsao.js`, `aluguel.js`, `grafico.js`, `chatui.js` | uma aba/recurso por arquivo |
| `scripts/` | rotinas que geram snapshots na branch `data` (não rodam no Render) e `build_css.sh` (roda no build); `logos_override/` = ajustes à mão dos logos |
| `tests/` | `test_*.py` (Python), `test_*.js` (Node) e `ui_smoke.cjs` (telas no celular, Playwright) |
| `android/` | app Android (WebView do site + widget Favoritos e grupos); como gerar o APK: README → **App Android** |
| `.github/workflows/` | `data.yml` (rotina diária de dados), `statusinvest.yml`, `ui-test.yml` (testes e telas em cada PR), `keepalive.yml` |

Crie arquivo novo só para um recurso novo e independente; caso contrário, estenda o arquivo do recurso.

---

## 3. Padrão estético

- **Tema escuro** (`<html class="dark">`), base `slate`. Primeiro o celular (360 px de largura), depois telas maiores.
- **Cores com significado fixo**: o significado oficial de cada cor está na seção **Cores** do painel ⓘ. Use a mesma cor para o mesmo
  sentido; significado novo → acrescente-o lá.
- **CSS próprio** usa as variáveis do design system (`var(--c-pos)`, `var(--bd)`, `var(--h)`, `var(--r)`…). Não escreva `rgb(...)` novo se já existe variável equivalente.
- **Tabelas** (todas): títulos de todas as colunas **centralizados** na horizontal e na vertical (inclusive "Ativo"); conteúdo da coluna Ativo **à esquerda**;
  conteúdo das demais colunas **centralizado**. Tabela nova segue o mesmo CSS (`.gtab`, `.kt-t`, `.pv-t`).
- **Formulários com nome ao lado do campo, um embaixo do outro**: classe `.frm` — nomes numa coluna alinhada à direita, campos
  começando no mesmo ponto e com a mesma largura (ex.: Critério/Início/Fim do Comparar).
- **Centralizado na vertical**: células de tabela, elementos lado a lado (nome + campo, ícone + texto, botões, selos, títulos de card) e
  conteúdo de cards ficam no meio da altura (`align-items: center`; `td, th` no design system). Exceção: texto corrido longo (chat, painel ⓘ) começa no topo.
- **Alinhamento em dúvida** (não se encaixa nas regras acima): pergunte ao dono do site antes de escolher.
- **Botões**: `.gbtn` (secundário), `.gbtn.pri` (ação principal), `.gbtn.dan` (perigo). Campos: `.pv-in`. Abas: `.tabs`. Selos: `.hb-*`.
- **Nunca** use `alert`, `confirm` ou `prompt` do navegador: use `uiAlert`, `uiConfirm`, `uiPrompt`, `uiChoose`, `uiToast`. Datas: `input type="date"`/`"month"` abrem o calendário do site (`uiCalendar`), não o do navegador.
  Carregando: `loaderHTML('texto')`.
- **Números** no formato brasileiro (`1.234,56`; `8,5%`; `R$ 1,2 bi`) com os utilitários do `ui.js`/`app.js`. Datas com `dataBR` (`dd/mm/aaaa`), horário de Brasília.
- **Textos**: curtos, no imperativo para botões ("Salvar", "Criar grupo"), mesmo nome do botão em todo o site.
  Renomeou um botão/aba → atualize o passo a passo do painel ⓘ que o cita (o chat lê os nomes da interface sozinho).
- **Tailwind**: o CSS é gerado no build a partir das classes encontradas em `index.html` e `*.js`.
  Escreva a classe **inteira** no código (`'text-rose-400'`), nunca montada por partes (`'text-' + cor + '-400'`) — a montada não entra no CSS.

---

## 4. Back-end e dados

- Toda coleta externa pode falhar ou ser bloqueada: tente ao vivo e caia para o snapshot (`snapshots.load`) — padrão já usado por Status Invest, TradingView e Yahoo.
  A queda vale para a **fonte inteira**, não para empresas soltas (seção 1.2).
- O servidor é o **plano gratuito do Render**: pouca CPU e RAM, disco apagado a cada reinício.
  Trabalho pesado é feito **uma vez** (na atualização dos dados ou nas rotinas de snapshot), nunca a cada visita.
  Respostas grandes reaproveitam o JSON pronto (`_json_fast`).
- A branch `data` guarda os snapshots e **não** dispara deploy. Código vai na `main`; dados, na `data`.
- Alertas de preço dos Favoritos: `grupos.js` (`screenerB3.alertas.v1`), conferidos a cada carga de dados (`dataload`).
- Chaves no `localStorage` seguem `screenerB3.<nome>.v<N>`. Mudou o formato salvo? Suba o `v<N>` (e migre se necessário) em vez de ler formato antigo como novo.
- Segredos (chave do Gemini, do Render etc.) ficam só nas variáveis de ambiente do Render/GitHub. Nunca no código, em commits ou no chat.

---

## 5. Fluxo de trabalho

0. Monte a lista do que vai mudar e **aguarde a mensagem "Pode fazer"** (seção 7). Pergunta se responde, sem executar.
1. Parta da `main` atualizada (`git fetch origin main` e crie/atualize sua branch a partir dela). Antes, confira se a publicação anterior no Render entrou no ar.
2. Faça a mudança seguindo as seções 1–4. Confira: a mudança copiou alguma informação que já existia? Se sim, troque por leitura da fonte.
3. Rode os testes (comandos no README → **Testes**). Corrigiu um bug do chat? Acrescente a pergunta que falhava em `tests/test_chat.py`.
4. Mudou algo visual? Confira no celular (aba afetada, tema escuro, textos sem cortar).
5. Commit com mensagem em português dizendo **o que** mudou e **por quê**. Um assunto por commit/PR.
6. PR para a `main`, merge, e dispare a publicação no Render (README → **Publicar**). Não fique acompanhando o deploy: ele é conferido no passo 1 da próxima alteração.
7. Atualize o README se mudou algo que o usuário ou quem publica precisa saber; atualize este arquivo se mudou uma regra ou a fonte de uma informação.

---

## 6. Não faça

- Copiar informação, função, tabela, lista de rótulos, texto de explicação ou bloco de CSS que já existe — leia da fonte ou parametrize.
- Misturar fontes dentro de um mesmo grupo de informação (seção 1.2).
- Escrever explicação, passo a passo, glossário ou lista de botões dentro do chat — o lugar é o painel ⓘ / a interface.
- Editar `?v=` dos scripts, `static/tw.css` ou arquivos em `cache/` (são gerados).
- Colocar segredos no repositório.
- Trazer bibliotecas novas sem necessidade (cada uma pesa no carregamento e no build do Render).
- Desligar, pular ou apagar testes para passar.

---

## 7. Trabalho com assistentes (Claude, Grok etc.)

- Pedido de alteração → o assistente responde com a **lista** do que vai mudar e só executa depois da mensagem **"Pode fazer"**.
  Pergunta → só responde e aguarda.
- Depois do merge, só dispara a publicação; confere se entrou no ar antes da próxima alteração.
- Captura de tela só em mudança de layout: poucas, recortadas na parte alterada. Mudança de texto/dado se confere sem imagem.
- Leia só o trecho necessário dos arquivos (`grep` e intervalos de linhas), não o arquivo inteiro.
- Respostas e descrições de PR curtas; alterações pequenas aprovadas juntas vão num só PR.
