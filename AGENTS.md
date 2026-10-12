# Diretrizes do projeto — Screener B3

Regras para quem altera este repositório (pessoas, Claude, Grok ou outro assistente). Leia antes de mudar qualquer coisa.
O `README.md` explica **o que o site faz e como rodar/publicar**; este arquivo explica **como mudar o código sem quebrar padrões**.
Nada aqui deve repetir o README: quando precisar de um detalhe dele, aponte a seção.

Idioma: português do Brasil em textos da interface, mensagens de commit, comentários e documentação.

---

## 1. Princípio central: uma fonte de verdade para cada informação

Toda informação existe em **um único lugar**. Os outros lugares **leem** dali, nunca copiam.
Assim, ao alterar a fonte, tudo que depende dela muda junto.

Antes de criar algo novo:
1. **Procure** se já existe (`grep` pelo nome, rótulo ou valor). Se existe, **use ou estenda**.
2. Se precisa de uma variação, **parametrize** a função/classe existente em vez de copiar.
3. Se um valor pode ser **calculado** a partir de outro, calcule — não guarde as duas versões.
4. Se for inevitável manter o mesmo dado em dois lugares (ex.: Python e HTML), deixe um comentário nos **dois** lados:
   `# manter em sincronia com <arquivo>:<nome>` — e registre o caso na seção 7.

### Onde cada informação mora

| Informação | Fonte única | Quem consome (não copiar lá) |
|---|---|---|
| Indicadores (chave, rótulo, unidade, direção, colunas das fontes, limiar) | `server.py` → `FIELDS` | `/api/data` → `fields` → filtros, cards, ordenação e CSV (`app.js`); chat (`chat.build`) |
| Fontes de dados (id, nome, logo, países) | `server.py` → `SOURCES` | seletor de fonte, contagens, status |
| Países e moedas | `tradingview.py` → `COUNTRIES` | `/api/countries`, seletor de país |
| Regras de consenso entre fontes | `consensus.py` | cores/badges dos cards (via `st`, `cm`, `ag` de cada linha) |
| Explicações ao usuário (regras, cores, como usar cada aba) | painel ⓘ — `#infoModal` em `index.html` | o chat lê esse painel (`chat.guide()`); não reescreva a explicação em outro lugar |
| Paleta, alturas, raios, sombras | `index.html` → bloco `/* Design system */` (`:root { --c-pos … }`) | todo CSS novo usa `var(--…)` |
| Diálogos, toast, carregamento | `ui.js` → `uiConfirm`, `uiAlert`, `uiPrompt`, `uiChoose`, `uiToast`, `loaderHTML` | todas as abas |
| Formatação de números/moeda e escape de HTML | `app.js` → `nf`, `fmt`, `fmtPrice`, `fmtBig`, `fmtMoneyBig`, `esc` | demais scripts (mesma página) |
| Média de preços por período | `ui.js` → `avgLastMonths` | grupos, previsão, testes |
| Lista de scripts JS servidos | `server.py` → `JS_FILES` + `<script>` no fim do `index.html` | ver seção 7 |
| Versão (`?v=`) de JS/CSS | **automática** (hash do conteúdo, `server._index_html`) | não edite `?v=` à mão |
| Dados de snapshots (branch `data`) | `snapshots.load(nome)` | nunca baixe a mesma URL por conta própria |

---

## 2. Mapa do código

| Arquivo | Responsabilidade |
|---|---|
| `server.py` | API FastAPI, montagem dos dados (`build`, `finalize`), cache, rotas, servir HTML/JS/CSS |
| `consensus.py` | consenso entre fontes (testado em `tests/test_consensus.py`) |
| `chat.py` | chat: entendimento sem IA (`parse`), respostas com dados (`execute`), Gemini (`interpret`, `gemini2`, `ground`) |
| `history.py`, `snapshots.py`, `statusinvest.py`, `tradingview.py`, `tiebreak.py` | histórico de preços, snapshots, coleta de cada fonte, desempate Yahoo |
| `index.html` | estrutura de todas as abas, CSS próprio (design system) e painel ⓘ |
| `ui.js` | componentes compartilhados (diálogos, toast, loader) e utilitários |
| `app.js` | aba Ações + formatadores e estado global (`state`) |
| `grupos.js`, `comparar.js`, `previsao.js`, `aluguel.js`, `grafico.js`, `chatui.js` | uma aba/recurso por arquivo |
| `scripts/` | rotinas que geram snapshots na branch `data` (não rodam no Render) e `build_css.sh` (roda no build) |
| `tests/` | `test_*.py` (Python) e `test_*.js` (Node) |

Crie arquivo novo só para um recurso novo e independente; caso contrário, estenda o arquivo do recurso.

---

## 3. Padrão estético

- **Tema escuro** (`<html class="dark">`), base `slate`. Primeiro o celular (360 px de largura), depois telas maiores.
- **Cores com significado fixo** — use sempre o mesmo para o mesmo sentido:
  verde = positivo/ganho/ação principal · rosa/vermelho = negativo/perda/excluir · âmbar = maioria com divergência ·
  vermelho de card = sem maioria · azul-claro = informação/EBIT ajustado · azul-escuro = banco/seguradora ·
  violeta = valorização total (Previsão) · amarelo = imposto (Previsão).
  A legenda oficial é a seção **Cores** do painel ⓘ; se criar um significado novo, adicione-o lá.
- **CSS próprio** usa as variáveis do design system (`var(--c-pos)`, `var(--bd)`, `var(--h)`, `var(--r)`…). Não escreva `rgb(...)` novo se já existe variável equivalente.
- **Botões**: `.gbtn` (secundário), `.gbtn.pri` (ação principal), `.gbtn.dan` (perigo). Campos: `.pv-in`. Abas: `.tabs`. Selos: `.hb-*`.
- **Nunca** use `alert`, `confirm` ou `prompt` do navegador: use `uiAlert`, `uiConfirm`, `uiPrompt`, `uiChoose`, `uiToast`.
  Carregando: `loaderHTML('texto')`.
- **Números** no formato brasileiro (`1.234,56`; `8,5%`; `R$ 1,2 bi`) com os formatadores de `app.js`. Datas `dd/mm/aaaa`, horário de Brasília.
- **Textos**: curtos, no imperativo para botões ("Salvar", "Criar grupo"), mesmo nome do botão em todo o site.
  Ao renomear um botão/aba, atualize também o painel ⓘ (e a seção 7 se o chat o cita).
- **Tailwind**: o CSS é gerado no build a partir das classes encontradas em `index.html` e `*.js`.
  Escreva a classe **inteira** no código (`'text-rose-400'`), nunca montada por partes (`'text-' + cor + '-400'`) — a montada não entra no CSS.

---

## 4. Back-end e dados

- Toda coleta externa pode falhar ou ser bloqueada: tente ao vivo e caia para o snapshot (`snapshots.load`) — padrão já usado por Status Invest, TradingView e Yahoo.
- O servidor é o **plano gratuito do Render**: pouca CPU e RAM, disco apagado a cada reinício.
  Trabalho pesado é feito **uma vez** (na atualização dos dados ou nas rotinas de snapshot), nunca a cada visita.
  Respostas grandes reaproveitam o JSON pronto (`_json_fast`).
- A branch `data` guarda os snapshots e **não** dispara deploy. Código vai na `main`; dados, na `data`.
- Chaves no `localStorage` seguem `screenerB3.<nome>.v<N>`. Mudou o formato salvo? Suba o `v<N>` (e migre se necessário) em vez de ler formato antigo como novo.
- Segredos (chave do Gemini, do Render etc.) ficam só nas variáveis de ambiente do Render/GitHub. Nunca no código, em commits ou no chat.

---

## 5. Fluxo de trabalho

1. Parta da `main` atualizada (`git fetch origin main` e crie/atualize sua branch a partir dela).
2. Faça a mudança seguindo as seções 1–4.
3. Rode os testes:
   ```bash
   python tests/test_consensus.py && python tests/test_chat.py
   for f in tests/*.js; do node "$f"; done
   ```
   Corrigiu um bug do chat? Acrescente a pergunta que falhava em `tests/test_chat.py`.
4. Mudou algo visual? Confira no celular (aba afetada, tema escuro, textos sem cortar).
5. Commit com mensagem em português dizendo **o que** mudou e **por quê**. Um assunto por commit/PR.
6. PR para a `main`, merge, e publique no Render (deploy hook ou API; o deploy automático pelo GitHub não está chegando ao Render).
   Depois do deploy, confira `/api/status` e a aba alterada.
7. Atualize o README se mudou algo que o usuário ou quem publica precisa saber; atualize este arquivo se mudou uma regra.

---

## 6. Não faça

- Copiar uma função, tabela, lista de rótulos ou bloco de CSS que já existe — reutilize ou parametrize.
- Editar `?v=` dos scripts, `static/tw.css` ou arquivos em `cache/` (são gerados).
- Colocar segredos no repositório.
- Trazer bibliotecas novas sem necessidade (cada uma pesa no carregamento e no build do Render).
- Desligar, pular ou apagar testes para passar.
- Deixar texto de explicação ao usuário fora do painel ⓘ quando ele já explica o assunto.

---

## 7. Duplicações conhecidas (manter em sincronia até unificar)

Lugares onde, hoje, a mesma informação aparece duas vezes. Ao mexer em um lado, ajuste o outro na mesma mudança.
Ao eliminar uma duplicação, remova-a desta lista.

| Informação | Lado A | Lado B |
|---|---|---|
| Lista de scripts | `server.py` → `JS_FILES` | `<script src="/static/…">` no fim do `index.html` |
| Nomes de botões/abas/opções que o chat pode citar | interface (`index.html` e `*.js`) | `chat.py` → `LABELS` |
| Passo a passo de cada aba | painel ⓘ (`#infoModal`) | `chat.py` → `HOWTO` |
| Explicação do consenso e glossário | painel ⓘ (`#infoModal`) | `chat.py` → `GLOSS` |
| Escape de HTML `esc` | `app.js` | cópias locais em `aluguel.js`, `chatui.js`, `comparar.js` (trocar pelo `esc` global) |
| Formatador `F2` (2 casas, pt-BR) | `app.js` → `nf(2)` | cópias locais em `comparar.js`, `grupos.js` |
| Configuração do Tailwind (`darkMode: 'class'`) | `tailwind.config.js` | `<script>tailwind.config …</script>` no `index.html` (usado só quando o CSS gerado não existe) |
