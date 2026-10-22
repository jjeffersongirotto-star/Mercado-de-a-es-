package com.jginvesting.app;

import org.json.JSONArray;
import org.json.JSONObject;

import java.text.DecimalFormat;
import java.text.DecimalFormatSymbols;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;

/** Dados do widget: lista dos Favoritos (vinda do site) e resposta de /api/widget. Sem dependência do Android (testável na JVM). */
public final class WidgetData {
    private WidgetData() { }

    /** Ticker aceito do site (Favoritos/grupos), do widget e de /api/widget: PETR4, KO, V, BRK.B, RR., BT-A, 7203.
     *  Letras, dígitos, ponto e hífen; começa com letra ou dígito; 1 a 12 caracteres (mesmo padrão de server.WIDGET_TK). */
    public static final String TICKER = "[A-Z0-9][A-Z0-9.\\-]{0,11}";
    public static boolean validTicker(String t) { return t != null && t.matches(TICKER); }

    /** Uma linha do widget. Campos nulos = sem dado ("—"). f = Barato/Caro em % (+ até o valor justo, − acima dele). */
    public static final class Item {
        public final String t, m;
        public final Double p, v, f;
        public final Integer g;  // Medo e Ganância da ação (0–100)
        public String s, l;      // nome curto da empresa e arquivo do logo (/logos/<l>; null = iniciais)
        public String c;         // moeda (USD, GBP, EUR, JPY; null = real)
        public String x;         // sem Barato/Caro: texto curto do servidor ("Prej.", "s/ VJ"; valor_justo.rotulo); null = "—"
        Item(String t, Double p, Double v, Double f, String m, Integer g) { this.t = t; this.p = p; this.v = v; this.f = f; this.m = m; this.g = g; }
    }

    /** Topo do widget com nome curto: [marca comprida][seletor][horário][⟳]. -> dp que sobram para a marca (o seletor fica colado
     *  ao horário). Estimativa sem medir texto: seletor = margens + "  ▾" + letras × 6,6dp (14sp negrito); fixo = margens do widget,
     *  ⟳ e horário (11sp). Texto cresce com a escala de fonte do aparelho. widthDp = largura atual (min/max conforme a tela). */
    public static float brandRoom(String name, int widthDp, float fontScale, boolean hasTime) {
        if (widthDp <= 0) return 0;
        float fs = fontScale > 0 ? fontScale : 1f;
        float chip = 22 + 16 + (12 + (name == null ? 0 : name.length()) * 6.6f) * fs;
        float fixed = 18 + 34 + (hasTime ? 62 * fs : 0);
        return widthDp - fixed - chip;
    }

    /** A marca comprida (no mínimo brandDp) cabe ao lado do seletor com este nome? Senão, o logo quadrado com o seletor no meio. */
    public static boolean longLogo(String name, int widthDp, int brandDp, float fontScale, boolean hasTime) {
        return widthDp > 0 && brandRoom(name, widthDp, fontScale, hasTime) >= brandDp;
    }

    /** Largura em px do gráfico da marca: nome sem distorcer (nameW) + gráfico esticado até roomPx, entre o mínimo (minW, a marca
     *  compacta) e 1,5× a largura natural (natW, proporção da faixa do site). */
    public static int brandGrafPx(int roomPx, int nameW, int minW, int natW) {
        return Math.max(minW, Math.min(roomPx - nameW, natW * 3 / 2));
    }

    /** Largura atual do widget em dp: retrato = largura mínima, paisagem = máxima (regra do AppWidgetManager); 0 = desconhecida. */
    public static int widthDp(int minW, int maxW, boolean landscape) { return landscape && maxW > 0 ? maxW : minW > 0 ? minW : maxW; }

    /** Altura (dp) do widget: em pé = altura máxima; deitado = mínima (o contrário da largura). */
    public static int heightDp(int minH, int maxH, boolean landscape) { return landscape ? (minH > 0 ? minH : maxH) : (maxH > 0 ? maxH : minH); }

    /** Títulos das colunas: 2 linhas de 10sp (≈11,7 por linha) + 4dp embaixo; cresce com a escala de fonte do aparelho. */
    public static float colsDp(float fontScale) { return 4 + 24 * Math.max(1f, fontScale); }

    /** Cabeçalho até a lista: margens (8 em cima, 6 embaixo) + barra 36 + aviso de atualização (4+28) + 6 + títulos + linha 1. */
    public static float headerDp(float fontScale, boolean upd) { return 8 + 36 + (upd ? 32 : 0) + 6 + colsDp(fontScale) + 1 + 6; }

    /** Linha base (dp): 46, ou nome em 2 linhas + ticker com fonte grande. */
    public static float rowBaseDp(float fontScale) { return Math.max(46f, 8 + 38 * fontScale); }

    /** Linhas inteiras na altura da lista: {n, altura de cada linha em px}. n = quantas linhas base cabem (com o divisor de 1dp);
     *  com itens para encher, a sobra é dividida entre as n linhas (até 1,6× a base) e a última termina rente à borda;
     *  com menos itens que n, linha base e o espaço fica vazio embaixo. Lista mais baixa que uma linha: 1 linha base. */
    public static int[] rows(int listPx, float density, float fontScale, int items) {
        int base = Math.round(rowBaseDp(fontScale) * density), div = Math.max(1, Math.round(density));
        int n = Math.max(1, (listPx + div) / (base + div));
        if (items < n || listPx < base) return new int[]{n, base};
        int h = (listPx - (n - 1) * div) / n;
        return new int[]{n, Math.min(h, Math.round(base * 1.6f))};
    }

    /** Largura (dp) da coluna Ação para o texto: widget − margens − colunas Preço/Dia/Barato/Caro/Medo (230dp) − slot do logo. */
    public static float nameRoomDp(int wDp, boolean narrow) { return Math.max(40, (wDp > 0 ? wDp : 300) - 18 - 230 - 4 - (narrow ? 0 : 40)); }

    /** Tamanho (sp) do nome em cima: o maior de 14 a 11 sp em que cabe numa linha (≈0,52 em por letra em negrito); não cabendo
     *  nem em 11, 12 sp em até 2 linhas (o layout permite 2) — nunca cortado no meio de uma palavra curta. */
    public static float nameSp(String s, float roomDp) {
        int n = s == null ? 0 : s.length();
        if (n * 0.52f * 14f <= roomDp) return 14f;
        if (s.trim().contains(" ")) return 12f;  // 1.21: mais de uma palavra que não cabe → 2 linhas (BB Seguridade como Caixa Seguridade)
        for (float sp = 13.5f; sp >= 11f; sp -= 0.5f) if (n * 0.52f * sp <= roomDp) return sp;
        return 12f;
    }

    /** Largura (dp) de um texto no tamanho sp (negrito ou não); no aparelho mede com Paint, nos testes por estimativa. */
    public interface Meas { float dp(String s, float sp, boolean bold); }

    /** Menor largura (dp) do nome em 2 linhas a 12 sp: a melhor quebra entre palavras. */
    static float twoLineDp(String s, Meas m) {
        String[] w = s.trim().split("\\s+");
        float best = m.dp(s, 12f, true);
        for (int i = 1; i < w.length; i++)
            best = Math.min(best, Math.max(m.dp(String.join(" ", java.util.Arrays.copyOfRange(w, 0, i)), 12f, true),
                    m.dp(String.join(" ", java.util.Arrays.copyOfRange(w, i, w.length)), 12f, true)));
        return best;
    }

    /** 1.21: coluna Ação do tamanho do maior nome. text = largura (dp) do texto da coluna (nome e ticker, sem o logo), sp = tamanho
     *  do nome de cada linha. Cada nome precisa de: 14 sp numa linha, ou (mais de uma palavra) 2 linhas a 12 sp se for mais estreito;
     *  a coluna = o maior desses (até room); depois cada nome usa 14 sp se couber numa linha, senão 2 linhas a 12 sp, senão (uma
     *  palavra) o maior de 13,5 a 11 sp que cabe. extra = o que sobra para as outras 4 colunas (dividido igualmente). */
    public static final class Cols {
        public final float text, extra; public final float[] sp;
        Cols(float text, float extra, float[] sp) { this.text = text; this.extra = extra; this.sp = sp; }
    }

    public static Cols cols(List<String> names, List<String> tickers, float room, Meas m) {
        int n = names.size(); float need = 0;
        float[] w14 = new float[n], w2 = new float[n];
        for (int i = 0; i < n; i++) {
            String s = names.get(i) == null ? "" : names.get(i);
            w14[i] = m.dp(s, 14f, true);
            w2[i] = s.trim().contains(" ") ? twoLineDp(s, m) : Float.MAX_VALUE;
            need = Math.max(need, Math.min(w14[i], w2[i]));
            String t = tickers.get(i);
            if (t != null && !t.isEmpty()) need = Math.max(need, m.dp(t, 10.5f, false));
        }
        float text = Math.min(room, (float) Math.ceil(need) + 2);  // +2: arredondamento da medida
        float[] sp = new float[n];
        for (int i = 0; i < n; i++) {
            String s = names.get(i) == null ? "" : names.get(i);
            if (w14[i] <= text) sp[i] = 14f;
            else if (w2[i] != Float.MAX_VALUE) sp[i] = 12f;
            else { sp[i] = 11f; for (float x = 13.5f; x >= 11f; x -= 0.5f) if (m.dp(s, x, true) <= text) { sp[i] = x; break; } }
        }
        return new Cols(text, Math.max(0, room - text), sp);
    }

    /** 1.23: uma versão do widget para o Android escolher pelo tamanho real (RemoteViews(Map<SizeF, RemoteViews>)).
     *  w, h = tamanho (dp) informado ao Android; lw = largura usada no desenho (marca comprida ou logo quadrado); land = deitado. */
    public static final class Size {
        public final int w, h, lw; public final boolean land;
        Size(int w, int h, int lw, boolean land) { this.w = w; this.h = h; this.lw = lw; this.land = land; }
        @Override public String toString() { return w + "x" + h + (land ? "L" : "P"); }
    }

    /** Nível do plano de versões: FULL = até 6 (a orientação atual e, se for diferente, a outra), FEW = 3 da orientação atual,
     *  ONE = uma só (resposta grande demais para o Android: ver Widgets.compose). */
    public static final int FULL = 0, FEW = 1, ONE = 2;

    /** 1.23: versões do widget. O Android (RemoteViews.findBestFitLayout) usa, entre as que cabem no tamanho real (largura E altura
     *  menores ou iguais), a mais próxima (distância ao quadrado); nenhuma cabe = a menor. Em pé o widget tem a largura mínima e a
     *  altura máxima; deitado, o contrário — e ao girar o Android troca a versão sozinho, sem chamar o app. Por isso, além das alturas
     *  perto da atual (o launcher pode errar), vão versões da outra orientação. Largura informada = a da orientação − 24 dp: cada
     *  orientação só cabe na própria largura (quando as larguras são bem diferentes) e a mais próxima ganha; a folga cobre launcher
     *  que informa um pouco mais largo do que é. Altura mínima de 80 dp; sem altura conhecida: uma versão com h = 0. */
    public static List<Size> sizes(int minW, int maxW, int minH, int maxH, boolean land, int level) {
        int h = heightDp(minH, maxH, land), oh = heightDp(minH, maxH, !land);
        int lw = widthDp(minW, maxW, land), olw = widthDp(minW, maxW, !land);
        List<Size> out = new ArrayList<>();
        if (h <= 0 || level >= ONE) { out.add(new Size(sizeW(lw), Math.max(0, h), lw, land)); return out; }
        boolean other = level == FULL && oh > 0 && (Math.abs(oh - h) >= 8 || Math.abs(olw - lw) >= 24);
        int[] cur = level == FEW ? new int[]{0, -16, -32} : other ? new int[]{16, 0, -16, -32} : new int[]{16, 0, -12, -24, -36, -48};
        for (int x : cur) add(out, new Size(sizeW(lw), h + x, lw, land));
        if (other) for (int x : new int[]{0, -16}) add(out, new Size(sizeW(olw), oh + x, olw, !land));
        if (out.isEmpty()) out.add(new Size(sizeW(lw), h, lw, land));
        return out;
    }
    private static int sizeW(int w) { return Math.max(1, w - 24); }
    private static void add(List<Size> out, Size s) {
        if (s.h < 80) return;
        for (Size o : out) if (o.w == s.w && o.h == s.h) return;
        out.add(s);
    }

    /** 1.23: o relógio do aparelho pode voltar (ajuste de hora, fuso): diferença negativa = janela vencida, nunca "para sempre".
     *  since = início (ms; 0 = nunca). Tolera SKEW_MS no futuro (marcas nextToken de toques no mesmo instante). */
    public static final long SKEW_MS = 1000;
    public static boolean within(long since, long now, long window) {
        if (since <= 0) return false;
        long d = now - since;
        return d >= -SKEW_MS && d < window;
    }

    /** Marca de um novo "Atualizando…": agora; se a guardada é deste instante (toques seguidos), a seguinte. Marca guardada muito
     *  no futuro (o relógio voltou) não conta — antes Math.max(agora, guardada + 1) a carregava e o aviso não sumia mais. */
    public static long nextToken(long cur, long now) { return cur >= now && cur - now < SKEW_MS ? cur + 1 : now; }

    /** 1.23: tempo (ms) para o próximo pedido dentro do prazo total (deadline, relógio do aparelho): o que falta, no máximo cap;
     *  0 = não vale começar (falta menos que min). O broadcast do widget tem ~10 s no total, não 10 s por pedido. */
    public static int budget(long deadline, long now, int cap, int min) {
        long r = deadline - now;
        return r < min ? 0 : (int) Math.min(cap, r);
    }

    /** Nome de arquivo para um texto qualquer (id de grupo, chave do Grupo simulação): 32 dígitos hex do SHA-256. */
    public static String fileKey(String s) {
        try {
            byte[] d = java.security.MessageDigest.getInstance("SHA-256").digest((s == null ? "" : s).getBytes(java.nio.charset.StandardCharsets.UTF_8));
            StringBuilder b = new StringBuilder();
            for (int i = 0; i < 16; i++) b.append(String.format("%02x", d[i] & 0xff));
            return b.toString();
        } catch (java.security.NoSuchAlgorithmException e) { throw new IllegalStateException(e); }
    }

    /** Chaves por widget (sel_ID, ssel_ID) quando o Android devolve widgets com ids novos (backup restaurado):
     *  -> o que gravar (chave nova -> valor) e o que apagar (chave -> null). Lê tudo antes de mudar (ids velhos e novos podem se cruzar). */
    public static Map<String, String> remap(Map<String, ?> all, String prefix, int[] oldIds, int[] newIds) {
        Map<String, String> out = new java.util.LinkedHashMap<>();
        int n = Math.min(oldIds == null ? 0 : oldIds.length, newIds == null ? 0 : newIds.length);
        for (int i = 0; i < n; i++) out.put(prefix + oldIds[i], null);
        for (int i = 0; i < n; i++) {
            Object v = all.get(prefix + oldIds[i]);
            if (v instanceof String) out.put(prefix + newIds[i], (String) v);
        }
        return out;
    }

    /** 1.23: junta pedidos seguidos (ponte do site: setFavs e setGroups ao abrir o app = uma busca só). claim() = true para o
     *  primeiro pedido, que agenda a busca; os seguintes, até ela começar (started), ficam com ela. Depois de começar, um pedido
     *  novo agenda outra (os dados podem ter mudado depois da leitura). */
    public static final class Coalesce {
        private boolean queued;
        public synchronized boolean claim() { if (queued) return false; queued = true; return true; }
        public synchronized void started() { queued = false; }
    }

    /** Arquivo de logo válido de /api/widget (hash de 12 dígitos .png) ou null. */
    public static String logo(String l) { return l != null && l.matches("[0-9a-f]{12}\\.png") ? l : null; }

    /** Iniciais do círculo quando a empresa não tem logo: 2 primeiras letras do ticker. */
    public static String initials(String t) { return t == null ? "" : t.substring(0, Math.min(2, t.length())); }

    /** Lado do bitmap do logo: slot de 32dp, arquivo de 64 px; com muitas linhas, menor. */
    // 1.11: até 12 linhas o logo vai na resolução real da tela (32dp × densidade, até 96 px; o arquivo tem 128 px) — antes 56 px ampliados = borrado
    public static int logoPx(float density, int rows) { return Math.min(Math.round(32 * density), rows > 24 ? 44 : rows > 12 ? 64 : 96); }

    /** Logos usados pelas linhas (sem repetir), para baixar os que faltam. */
    public static List<String> logos(List<Item> items) {
        List<String> out = new ArrayList<>();
        for (Item it : items) if (it.l != null && !out.contains(it.l)) out.add(it.l);
        return out;
    }

    /** Lista de favoritos (JSON ["PETR4", ...], na ordem do site) -> tickers válidos, sem repetir. */
    public static List<String> favs(String json) {
        List<String> out = new ArrayList<>();
        if (json == null || json.isEmpty()) return out;
        try {
            JSONArray a = new JSONArray(json);
            for (int i = 0; i < a.length(); i++) {
                String t = a.optString(i, "").trim().toUpperCase(Locale.ROOT);
                if (validTicker(t) && !out.contains(t)) out.add(t);
            }
        } catch (Exception e) { /* lista inválida = vazia */ }
        return out;
    }

    /** Um grupo da aba Grupos (id, nome e ações na ordem do quadro). */
    public static final class Group {
        public final String id, name; public final List<String> t;
        Group(String id, String name, List<String> t) { this.id = id; this.name = name; this.t = t; }
    }
    public static final String FAV = "fav", FAV_NAME = "Favoritos";
    public static final int MAX_ROWS = 40;  // mesmo limite de /api/widget
    public static List<Group> groups(String json) {
        List<Group> out = new ArrayList<>();
        try {
            JSONArray a = new JSONArray(json);
            for (int i = 0; i < a.length(); i++) {
                JSONObject o = a.getJSONObject(i);
                String id = o.optString("id", ""), n = o.optString("n", "");
                List<String> t = favs(o.optJSONArray("t") == null ? "[]" : o.getJSONArray("t").toString());
                if (!id.isEmpty() && !n.isEmpty() && !t.isEmpty() && !FAV.equals(id)) out.add(new Group(id, n, t.size() > MAX_ROWS ? t.subList(0, MAX_ROWS) : t));
            }
        } catch (Exception e) { /* sem grupos */ }
        return out;
    }
    /** Ações da lista escolhida: Favoritos ou o grupo (grupo que sumiu = vazio; o widget volta aos Favoritos). */
    public static List<String> tickers(String sel, String favsJson, List<Group> gs) {
        if (FAV.equals(sel)) { List<String> f = favs(favsJson); return f.size() > MAX_ROWS ? f.subList(0, MAX_ROWS) : f; }
        for (Group g : gs) if (g.id.equals(sel)) return g.t;
        return new ArrayList<>();
    }
    public static String name(String sel, List<Group> gs) {
        for (Group g : gs) if (g.id.equals(sel)) return g.name;
        return FAV_NAME;
    }
    public static boolean exists(String sel, List<Group> gs) {
        if (FAV.equals(sel)) return true;
        for (Group g : gs) if (g.id.equals(sel)) return true;
        return false;
    }

    /** Resposta de /api/widget pedida no instante req (relógio monotônico) substitui a guardada (pedida em stored)? Só se for mais nova:
     *  com trocas rápidas de grupo (A→B→A) ou ⟳ repetido, uma resposta lenta e antiga não apaga a mais recente da mesma lista. */
    public static boolean accept(long req, long stored) { return req >= stored; }

    /** Atualização em andamento iniciada em token terminou: só limpa o "Atualizando…" se ninguém começou outra depois. */
    public static boolean ownsLoading(long token, long current) { return current == token; }

    /** Logo da linha: o arquivo da própria ação (mesma resposta que deu preço e variação) se já está no aparelho; senão null
     *  (iniciais). Nunca o de outra linha ou de outro grupo. */
    public static String logoFile(Item it, java.util.function.Predicate<String> have) {
        return it != null && it.l != null && have.test(it.l) ? it.l : null;
    }

    /** Parâmetro t= de /api/widget. */
    public static String param(List<String> favs) {
        StringBuilder b = new StringBuilder();
        for (String t : favs) { if (b.length() > 0) b.append(','); b.append(t); }
        return b.toString();
    }

    /** Resposta de /api/widget -> itens na ordem dos favoritos (ticker sem dado no servidor aparece com "—"). */
    public static List<Item> items(List<String> favs, String json) {
        Map<String, Item> by = new HashMap<>();
        try {
            JSONArray r = new JSONObject(json).optJSONArray("r");
            for (int i = 0; r != null && i < r.length(); i++) {
                JSONObject o = r.getJSONObject(i);
                String t = o.optString("t", "");
                Double g = num(o, "g");
                Item it = new Item(t, num(o, "p"), num(o, "v"), num(o, "f"), o.isNull("m") ? null : o.optString("m", null), g == null ? null : (int) Math.round(g));
                it.s = o.isNull("s") ? null : o.optString("s", null);
                it.l = logo(o.isNull("l") ? null : o.optString("l", null));
                it.c = cur(o.isNull("c") ? null : o.optString("c", null));
                it.x = o.isNull("x") ? null : o.optString("x", null);
                by.put(t, it);
            }
        } catch (Exception e) { /* sem dados: só os tickers */ }
        List<Item> out = new ArrayList<>();
        for (String t : favs) { Item it = by.get(t); out.add(it != null ? it : new Item(t, null, null, null, null, null)); }
        return out;
    }

    /** "Atualizando…" some sozinho depois disso (⟳ espera o servidor refazer os dados: até RefreshJob.WAIT_MS + a busca). */
    public static final long LOADING_MS = 180_000;
    /** "Atualizando…" do widget Grupo simulação (sem espera do servidor) e validade do gráfico de 5 anos guardado. */
    public static final long SIM_LOADING_MS = 90_000, CHART_FRESH_MS = 6 * 3600_000L;

    /** Horário que o widget mostra: quando a resposta chegou (fim da atualização), "dd/MM HH:mm" no fuso do aparelho. */
    public static String fetched(long ms, java.util.TimeZone tz) {
        java.text.SimpleDateFormat f = new java.text.SimpleDateFormat("dd/MM HH:mm", java.util.Locale.US); f.setTimeZone(tz);
        return f.format(new java.util.Date(ms));
    }

    /** O servidor ainda está refazendo os dados? (resposta de /api/refresh ou /api/status; null/erro = não) */
    public static boolean refreshing(String json) {
        try { return json != null && new JSONObject(json).optBoolean("refreshing", false); } catch (Exception e) { return false; }
    }

    /** Horário dos dados no site (u, "dd/mm/aaaa hh:mm:ss", Brasília) -> "dd/mm hh:mm". */
    public static String updated(String json) {
        try {
            String u = new JSONObject(json).optString("u", "");
            return u.length() >= 16 ? u.substring(0, 5) + " " + u.substring(11, 16) : "";
        } catch (Exception e) { return ""; }
    }

    private static Double num(JSONObject o, String k) {
        if (!o.has(k) || o.isNull(k)) return null;
        double d = o.optDouble(k, Double.NaN);
        return Double.isNaN(d) ? null : d;
    }

    private static DecimalFormat df(String pat) { return new DecimalFormat(pat, DecimalFormatSymbols.getInstance(new Locale("pt", "BR"))); }

    /** Código de moeda válido (3 letras) ou null (= real). */
    public static String cur(String c) { return c != null && c.matches("[A-Z]{3}") ? c : null; }

    /** Símbolo da moeda, como o site (app.js → CUR). */
    public static String symbol(String cur) {
        if (cur == null || "BRL".equals(cur)) return "R$";
        switch (cur) { case "USD": return "US$"; case "EUR": return "€"; case "GBP": return "£"; case "JPY": return "¥"; default: return cur; }
    }

    /** R$ 1.234,56 (formato brasileiro, como no site). */
    public static String price(Double p) { return price(p, null); }

    /** Preço na moeda da ação, compacto para a coluna: US$ 343,46 · ¥ 3.094 (iene sem centavos, como o site) ·
     *  US$ 12.345 (de 10 mil para cima sem centavos) · US$ 1,07 mi (de 1 milhão para cima). */
    public static String price(Double p, String cur) {
        if (p == null) return "—";
        double a = Math.abs(p);
        String n = a >= 1e6 ? df("#,##0.00").format(p / 1e6) + " mi" : (a >= 10000 || "JPY".equals(cur)) ? df("#,##0").format(p) : df("#,##0.00").format(p);
        return symbol(cur) + " " + n;
    }

    /** Variação do dia: ▲ 1,23% / ▼ 0,55% (como no card). */
    public static String change(Double v) {
        if (v == null) return "—";
        return (v >= 0 ? "▲ " : "▼ ") + df("0.00").format(Math.abs(v)) + "%";
    }

    /** 1.24: quanto o preço mudou no dia, embaixo da % (+0,27 / -12,45), tirado do preço e da % que a linha já tem:
     *  p − p ÷ (1 + v/100); iene e valores de 10 mil para cima sem centavos (como price). Sem variação: "". */
    public static String changeAbs(Double p, Double v, String cur) {
        if (p == null || v == null || v <= -100) return "";
        double d = p - p / (1 + v / 100), a = Math.abs(d);
        String n = (a >= 10000 || "JPY".equals(cur)) ? df("#,##0").format(a) : df("#,##0.00").format(a);
        return (d < 0 && !n.matches("[0,.]+") ? "-" : "+") + n;
    }

    /** Barato/Caro como no card: +43% (verde: o preço precisa subir até o valor justo) ou −75% (vermelho). */
    public static String badge(Double f) { return badge(f, null); }

    /** Barato/Caro que arredonda para 0% (o servidor já manda 0: valor_justo.FAIR["zero"]): "0%" no chip verde, sem sinal. */
    public static boolean zero(Double f) { return f != null && Math.abs(f) < 0.5; }
    /** Chip verde (preço até o valor justo, inclusive 0%) ou vermelho. */
    public static boolean up(Double f) { return f != null && (f >= 0 || zero(f)); }

    /** Sem Barato/Caro: o texto curto do servidor (x, até 6 letras para caber no chip) ou "—". */
    public static String badge(Double f, String x) {
        if (f == null) return x != null && !x.isEmpty() && x.length() <= 6 ? x : "—";
        if (zero(f)) return "0%";
        DecimalFormat d = df("0"); d.setRoundingMode(java.math.RoundingMode.HALF_UP);  // como o site (Intl: metade para cima)
        return (f >= 0 ? "+" : "−") + d.format(Math.abs(f)) + "%";
    }

    /** Rótulo do eixo do gráfico: real como antes (R$ 59,68); outra moeda só o número, para caber na margem (a moeda está na dica). */
    public static String axis(double v, String cur) {
        if (cur == null || "BRL".equals(cur)) return price(v);
        double a = Math.abs(v);
        return a >= 1e6 ? df("#,##0.0").format(v / 1e6) + " mi" : (a >= 100 || "JPY".equals(cur)) ? df("#,##0").format(v) : df("#,##0.00").format(v);
    }

    // ---------- Medo e Ganância da ação (faixas de /api/widget → gf, as mesmas do card: snapshot fg_acoes) ----------
    /** Faixas [[25,"Medo extremo"],[45,"Medo"],...] -> limites e nomes. */
    public static final class Bands {
        public final int[] lim; public final String[] name;
        Bands(int[] lim, String[] name) { this.lim = lim; this.name = name; }
        /** Índice da faixa do valor (0 = medo extremo … 4 = ganância extrema), como fgBand do site. */
        public int index(int v) { for (int i = 0; i < lim.length; i++) if (v <= lim[i]) return i; return lim.length - 1; }
        /** Nome curto para a coluna: "Medo extremo" -> "Medo ext.". */
        public String shortName(int v) { return lim.length == 0 ? "" : name[index(v)].replace(" extremo", " ext.").replace(" extrema", " ext."); }
    }
    public static Bands bands(String json) {
        try {
            JSONArray a = new JSONObject(json).optJSONArray("gf");
            int n = a == null ? 0 : a.length(); int[] lim = new int[n]; String[] nm = new String[n];
            for (int i = 0; i < n; i++) { JSONArray f = a.getJSONArray(i); lim[i] = f.getInt(0); nm[i] = f.getString(1); }
            return new Bands(lim, nm);
        } catch (Exception e) { return new Bands(new int[0], new String[0]); }
    }

    // ---------- Gráfico de 5 anos (/api/widget/chart) ----------
    /** Série do gráfico: t em segundos, c = fechamento; base = preço no início do período (variação = c ÷ base − 1). */
    public static final class Chart {
        public final long[] t; public final double[] c; public final double base;
        public String cur;  // moeda (null = real)
        Chart(long[] t, double[] c, double base) { this.t = t; this.c = c; this.base = base; }
        public int size() { return t.length; }
    }
    public static Chart chart(String json) {
        try {
            JSONObject o = new JSONObject(json); JSONArray p = o.getJSONArray("p");
            int n = p.length(); if (n < 2 || o.isNull("b")) return null;
            long[] t = new long[n]; double[] c = new double[n];
            for (int i = 0; i < n; i++) { JSONArray q = p.getJSONArray(i); t[i] = q.getLong(0); c[i] = q.getDouble(1); }
            Chart ch = new Chart(t, c, o.getDouble("b"));
            ch.cur = cur(o.isNull("c") ? null : o.optString("c", null));
            return ch;
        } catch (Exception e) { return null; }
    }
    /** Toque na faixa z (0..n-1) do gráfico: data em z ÷ (n − 1) do período (1ª faixa = início, última = hoje) e o ponto =
     *  último fechamento até essa data (como a mira do site). */
    public static int zonePoint(Chart ch, int z, int n) {
        long x0 = ch.t[0], x1 = ch.t[ch.size() - 1];
        double at = x0 + (n > 1 ? z / (double) (n - 1) : 1) * (x1 - x0);
        int k = 0;
        for (int i = 0; i < ch.size(); i++) { if (ch.t[i] > at) break; k = i; }
        return k;
    }
    /** Dica do ponto, como a do gráfico do site: 16/10/2026 · R$ 59,68 · +101,62% (variação desde o início do período; moeda da ação). */
    public static String tip(Chart ch, int i) {
        java.text.SimpleDateFormat f = new java.text.SimpleDateFormat("dd/MM/yyyy", Locale.ROOT);
        f.setTimeZone(java.util.TimeZone.getTimeZone("America/Sao_Paulo"));
        double v = (ch.c[i] / ch.base - 1) * 100;
        return f.format(new java.util.Date(ch.t[i] * 1000)) + " · " + price(ch.c[i], ch.cur) + " · " + (v >= 0 ? "+" : "-") + df("#,##0.00").format(Math.abs(v)) + "%";
    }
}
