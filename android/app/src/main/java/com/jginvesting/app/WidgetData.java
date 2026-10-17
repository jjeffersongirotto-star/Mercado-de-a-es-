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

    /** Uma linha do widget. Campos nulos = sem dado ("—"). f = Barato/Caro em % (+ até o valor justo, − acima dele). */
    public static final class Item {
        public final String t, m;
        public final Double p, v, f;
        public final Integer g;  // Medo e Ganância da ação (0–100)
        public String s, l;      // nome curto da empresa e arquivo do logo (/logos/<l>; null = iniciais)
        Item(String t, Double p, Double v, Double f, String m, Integer g) { this.t = t; this.p = p; this.v = v; this.f = f; this.m = m; this.g = g; }
    }

    /** Arquivo de logo válido de /api/widget (hash de 12 dígitos .png) ou null. */
    public static String logo(String l) { return l != null && l.matches("[0-9a-f]{12}\\.png") ? l : null; }

    /** Iniciais do círculo quando a empresa não tem logo: 2 primeiras letras do ticker. */
    public static String initials(String t) { return t == null ? "" : t.substring(0, Math.min(2, t.length())); }

    /** Lado do bitmap do logo: slot de 32dp, arquivo de 64 px; com muitas linhas, menor. */
    public static int logoPx(float density, int rows) { return Math.min(Math.round(32 * density), rows > 24 ? 44 : 56); }

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
                if (t.matches("[A-Z0-9]{3,12}") && !out.contains(t)) out.add(t);
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

    /** R$ 1.234,56 (formato brasileiro, como no site). */
    public static String price(Double p) { return p == null ? "—" : "R$ " + df("#,##0.00").format(p); }

    /** Variação do dia: ▲ 1,23% / ▼ 0,55% (como no card). */
    public static String change(Double v) {
        if (v == null) return "—";
        return (v >= 0 ? "▲ " : "▼ ") + df("0.00").format(Math.abs(v)) + "%";
    }

    /** Barato/Caro como no card: +43% (verde: o preço precisa subir até o valor justo) ou −75% (vermelho). */
    public static String badge(Double f) {
        if (f == null) return "—";
        return (f >= 0 ? "+" : "−") + df("0").format(Math.abs(f)) + "%";
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
        Chart(long[] t, double[] c, double base) { this.t = t; this.c = c; this.base = base; }
        public int size() { return t.length; }
    }
    public static Chart chart(String json) {
        try {
            JSONObject o = new JSONObject(json); JSONArray p = o.getJSONArray("p");
            int n = p.length(); if (n < 2 || o.isNull("b")) return null;
            long[] t = new long[n]; double[] c = new double[n];
            for (int i = 0; i < n; i++) { JSONArray q = p.getJSONArray(i); t[i] = q.getLong(0); c[i] = q.getDouble(1); }
            return new Chart(t, c, o.getDouble("b"));
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
    /** Dica do ponto, como a do gráfico do site: 16/10/2026 · R$ 59,68 · +101,62% (variação desde o início do período). */
    public static String tip(Chart ch, int i) {
        java.text.SimpleDateFormat f = new java.text.SimpleDateFormat("dd/MM/yyyy", Locale.ROOT);
        f.setTimeZone(java.util.TimeZone.getTimeZone("America/Sao_Paulo"));
        double v = (ch.c[i] / ch.base - 1) * 100;
        return f.format(new java.util.Date(ch.t[i] * 1000)) + " · " + price(ch.c[i]) + " · " + (v >= 0 ? "+" : "-") + df("#,##0.00").format(Math.abs(v)) + "%";
    }
}
