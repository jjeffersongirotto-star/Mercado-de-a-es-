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

    /** Largura (dp) da coluna Ação para o texto: widget − margens − colunas Preço/Dia/Barato/Caro/Medo (230dp) − slot do logo. */
    public static float nameRoomDp(int wDp, boolean narrow) { return Math.max(40, (wDp > 0 ? wDp : 300) - 18 - 230 - 4 - (narrow ? 0 : 40)); }

    /** Tamanho (sp) do nome em cima: o maior de 14 a 11 sp em que cabe numa linha (≈0,52 em por letra em negrito); não cabendo
     *  nem em 11, 12 sp em até 2 linhas (o layout permite 2) — nunca cortado no meio de uma palavra curta. */
    public static float nameSp(String s, float roomDp) {
        int n = s == null ? 0 : s.length();
        for (float sp = 14f; sp >= 11f; sp -= 0.5f) if (n * 0.52f * sp <= roomDp) return sp;
        return 12f;
    }

    /** Arquivo de logo válido de /api/widget (hash de 12 dígitos .png) ou null. */
    public static String logo(String l) { return l != null && l.matches("[0-9a-f]{12}\\.png") ? l : null; }

    /** Iniciais do círculo quando a empresa não tem logo: 2 primeiras letras do ticker. */
    public static String initials(String t) { return t == null ? "" : t.substring(0, Math.min(2, t.length())); }

    /** Lado do bitmap do logo: slot de 32dp, arquivo de 64 px; com muitas linhas, menor. */
    // 1.11: até 12 linhas o logo vai na resolução real da tela (32dp × densidade, até 96 px; o arquivo tem 128 px) — antes 56 px ampliados = borrado
    public static int logoPx(float density, int rows) { return Math.min(Math.round(32 * density), rows > 24 ? 44 : rows > 12 ? 64 : 96); }

    /** Bytes de bitmap que o widget manda de uma vez: logos (ARGB) de todas as linhas + o gráfico aberto (RGB_565, escala até 1,5).
     *  O Android recusa a atualização acima de ~1 MB. */
    public static long bitmapBytes(int rows, float density, int wDp) {
        int px = logoPx(density, rows);
        float d = Math.min(1.5f, density);
        return (long) rows * px * px * 4 + (long) ((wDp - 20) * d) * (long) (110 * d) * 2;
    }

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
