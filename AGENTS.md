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
| Barato/Caro (valor justo: Graham; Gordon em bancos e seguradoras; P/VP do setor em holdings e imobiliárias) | `valor_justo.py` → `FAIR` (custo de capital, crescimento, subsetores, mínimo de empresas, teto do lucro) e `fair`; `server.lucro_pl` → `ln3`, `roe3`; o site faz a mesma conta em `app.js` → `fairOf` (configuração em `/api/data` → `fair`, respeita o seletor de fonte) | card (Ações e Grupos), grupo Baratas pelo Graham (`grupos.js`), chat (`chat.fair`) |
| Índice de Medo e Ganância da B3 (0–100, diário desde 1997; faixas e partes) | snapshot `fg` (`scripts/build_fg.py`: COTAHIST, fluxo B3, CDI; rotina diária) → `/api/fg` | velocímetro (`medo.js` → `fgLoad`, `fgBand`), Comparar, chat (`chat.fg_answer`) |
| Modelos da Previsão (regras, custos, IR, grupos prontos do rodízio, referências CDB e Ouro) | `modelos.py` → `MODELOS`, `REF`, `GRUPOS`, `HIB` (híbrido; explicação no painel ⓘ → **Modelos da Previsão**) | `/api/modelos` → card Modelos, abas Tabela/Desempenho (`previsao.js`); `/api/modelos/comparar` (`modelos.compare`, `ranking`, `top_sector`) → Comparar → Modelos (`comparar.js` → `modRun`, `modHtml`); chat |
| Sinais semanais dos modelos (índice da ação, média de 200 dias, alta em 12 meses, chance do algoritmo 1 e 3 meses, lucro no último balanço publicado) | snapshot `modelos` (`scripts/build_modelos.py`; lucro de `fund.json` ← `scripts/build_fund.py`, DFP da CVM; "mercado" de `build_fg.market`, índice da ação de `medo.stock_index`; CDB de `history.bcb`) | `modelos.py` |
| Aporte e retirada de cada mês da Previsão | `previsao.js` → `flows` | tabela da Previsão e simulação dos modelos |
| Comparar → Medo e Ganância de uma ação (índice da ação: `medo.stock_index`, mesma nota 0–100 de `medo.rank` usada pelo índice do mercado; altas/quedas semanais, demais mensais) | `medo.py` → `analyze` (histórico diário completo `history.b3full`, snapshot `fg`, Ibovespa) → `/api/fgcmp` | aba Comparar (`comparar.js` → `fgRun`, `fgHtml`) |
| Métodos de investimento (Barsi, Bazin, Graham, Buffett, Fórmula Mágica…) | painel ⓘ → seção **Métodos de investimento** | usuário; chat (`chat.method`, critérios em `METHODS`) |
| Carteira (compras e vendas) | `localStorage` `screenerB3.carteira.v2` no aparelho (`carteira.js`); posição, preço médio e proventos calculados do histórico | aba Carteira, Exportar/Importar |
| Utilitários do navegador: `esc`, `nf`, `F0`, `F2`, `pc`, `brl`, `norm`, `dataBR`, `parseBR`, `avgLastMonths`, `getRetry`, `fileIc`, `saveJSON` (Exportar) | `ui.js` (topo) | todos os scripts |
| Diálogos, toast, carregamento, Reorganizar (arrastar ⠿), calendário | `ui.js` → `uiConfirm`, `uiAlert`, `uiPrompt`, `uiChoose`, `uiToast`, `uiReorder`, `loaderHTML`, `uiCalendar` (todo `input type=date/month` vira `uiDateField` sozinho) | todas as abas |
| Formatação de indicadores (`fmt`, `fmtPrice`, `fmtBig`, `fmtMoneyBig`) e preço exibido (`priceOf`) | `app.js` | aba Ações, Comparar, Carteira |
| Rendimento dos índices entre duas datas (Ibovespa, CDB…) | `server._idx_returns` | Comparar e chat (`/api/returns`), Carteira (`/api/idxret`) |
| Lista de scripts JS | tags `<script src="/static/…">` do `index.html` | servidor (`JS_FILES` é lido delas) |
| Versão (`?v=`) de JS/CSS | **automática** (hash do conteúdo, `server._index_html`) | não edite `?v=` à mão |
| Configuração do Tailwind | `tailwind.config.js` | build do CSS e, sem ele, o CDN no navegador |
| App instalável: nome e cor | `<title>` e `<meta name="theme-color">` do `index.html` | manifesto (`/manifest.webmanifest`, gerado pelo servidor) |
| App instalável: desenho do ícone ("JG Investing") | `scripts/icon-source.jpg` (quadrada) e `scripts/icon-source-round.jpg` (redonda, Android); `scripts/build_icons.py` gera `static/icons/` — não edite os PNG à mão | manifesto, tela inicial do celular |
| Marca no topo do site (faixa "JG Investing") | `scripts/brand-source.jpg` (celular) e `scripts/brand-source-wide.jpg` (computador); `scripts/build_icons.py` gera `static/brand/` | cabeçalho do `index.html` (igual em todas as abas) |
| Nome do site/app ("JG Investing") | `index.html` → `<title>` (parte antes de " — ") | manifesto (`server.manifest`), chat e Gemini (`chat.site_name`) |
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
| `app.js` | aba Ações, estado global (`state`) e formatação de indicadores |
| `grupos.js`, `carteira.js`, `medo.js`, `comparar.js`, `previsao.js`, `aluguel.js`, `grafico.js`, `chatui.js` | uma aba/recurso por arquivo |
| `scripts/` | rotinas que geram snapshots na branch `data` (não rodam no Render) e `build_css.sh` (roda no build) |
| `tests/` | `test_*.py` (Python), `test_*.js` (Node) e `ui_smoke.cjs` (telas no celular, Playwright) |
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
