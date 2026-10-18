package com.jginvesting.app;

import org.json.JSONArray;
import org.json.JSONObject;

import java.text.DecimalFormat;
import java.text.DecimalFormatSymbols;
import java.util.ArrayList;
import java.util.List;
import java.util.Locale;

/** Dados do widget Grupo simulação: grupos de simulação vindos do site (grupos.js → pushSims) e resposta de /api/widget/simgrupo.
 *  Sem dependência do Android (testável na JVM). */
public final class SimData {
    private SimData() { }

    /** Um grupo de simulação da aba Grupos: nome (= id), data inicial (AAAA-MM) e valor inicial. */
    public static final class Sim {
        public final String id, name, di; public final double v0;
        Sim(String id, String name, String di, double v0) { this.id = id; this.name = name; this.di = di; this.v0 = v0; }
    }

    /** Uma posição de um modelo: ticker, nome popular (ou null), nº de ações, valor investido e valor atual. */
    public static final class Pos {
        public final String t, s; public final long q; public final double inv, v;
        Pos(String t, String s, long q, double inv, double v) { this.t = t; this.s = s; this.q = q; this.inv = inv; this.v = v; }
    }

    /** Uma linha do widget: modelo, valor aportado, valor atual, variação do dia (R$ e %), caixa no CDB e as maiores posições. */
    public static final class Row {
        public final String m, n; public final double ap, v, dv, cash; public final Double dp; public final int np;
        public final List<Pos> pos = new ArrayList<>();
        Row(String m, String n, double ap, double v, double dv, Double dp, double cash, int np) {
            this.m = m; this.n = n; this.ap = ap; this.v = v; this.dv = dv; this.dp = dp; this.cash = cash; this.np = np;
        }
    }

    private static final String DI = "\\d{4}-\\d{2}", MID = "[a-z0-9_]{1,24}";
    public static boolean validModel(String m) { return m != null && m.matches(MID); }

    /** JSON [{id, n, di, v0}] do site -> grupos válidos (nome até 80 letras, data AAAA-MM, valor > 0), sem repetir o id. */
    public static List<Sim> sims(String json) {
        List<Sim> out = new ArrayList<>();
        try {
            JSONArray a = new JSONArray(json);
            for (int i = 0; i < a.length() && out.size() < 30; i++) {
                JSONObject o = a.getJSONObject(i);
                String id = o.optString("id", ""), n = o.optString("n", id), di = o.optString("di", "");
                double v0 = o.optDouble("v0", 0);
                if (id.isEmpty() || id.length() > 80 || !di.matches(DI) || !(v0 > 0)) continue;
                boolean dup = false; for (Sim s : out) if (s.id.equals(id)) dup = true;
                if (!dup) out.add(new Sim(id, n.isEmpty() ? id : n, di, v0));
            }
        } catch (Exception e) { /* sem grupos */ }
        return out;
    }

    public static Sim find(String id, List<Sim> ss) { for (Sim s : ss) if (s.id.equals(id)) return s; return null; }

    /** Grupo escolhido no widget; o que sumiu (ou nenhum escolhido) = o primeiro; sem grupos = null. */
    public static Sim pick(String sel, List<Sim> ss) { Sim s = find(sel == null ? "" : sel, ss); return s != null ? s : ss.isEmpty() ? null : ss.get(0); }

    /** Chave da resposta guardada: muda quando a data ou o valor inicial do grupo mudam (resposta antiga não vale). */
    public static String key(Sim s) { return s == null ? "" : s.id + "|" + s.di + "|" + s.v0; }

    /** Parâmetros de /api/widget/simgrupo. */
    public static String query(Sim s) {
        try { return "di=" + java.net.URLEncoder.encode(s.di, "UTF-8") + "&v0=" + new DecimalFormat("0.##", DecimalFormatSymbols.getInstance(Locale.ROOT)).format(s.v0); }
        catch (Exception e) { return ""; }
    }

    /** Resposta de /api/widget/simgrupo -> linhas (na ordem do servidor: maior valor atual primeiro). */
    public static List<Row> rows(String json) {
        List<Row> out = new ArrayList<>();
        try {
            JSONArray r = new JSONObject(json).optJSONArray("r");
            for (int i = 0; r != null && i < r.length(); i++) {
                JSONObject o = r.getJSONObject(i);
                String m = o.optString("m", "");
                if (!validModel(m)) continue;
                Row row = new Row(m, o.optString("n", m), o.optDouble("ap", 0), o.optDouble("v", 0), o.optDouble("dv", 0),
                        o.isNull("dp") || !o.has("dp") ? null : o.optDouble("dp"), o.optDouble("cash", 0), o.optInt("np", 0));
                JSONArray p = o.optJSONArray("pos");
                for (int k = 0; p != null && k < p.length(); k++) {
                    JSONObject q = p.getJSONObject(k);
                    String t = q.optString("t", "");
                    if (!WidgetData.validTicker(t)) continue;
                    row.pos.add(new Pos(t, q.isNull("s") ? null : q.optString("s", null), q.optLong("q", 0), q.optDouble("inv", 0), q.optDouble("v", 0)));
                }
                out.add(row);
            }
        } catch (Exception e) { /* sem dados */ }
        return out;
    }

    /** Horário dos dados no site (u, "dd/mm/aaaa hh:mm:ss") -> "dd/mm hh:mm" (mesma regra do widget Favoritos). */
    public static String updated(String json) { return WidgetData.updated(json); }

    private static DecimalFormat df(String pat) { return new DecimalFormat(pat, DecimalFormatSymbols.getInstance(new Locale("pt", "BR"))); }

    /** Valor compacto para a coluna: R$ 950,40 · R$ 12.345 (de mil para cima sem centavos) · R$ 1,23 mi. */
    public static String money(double v) {
        double a = Math.abs(v);
        String n = a >= 1e6 ? df("#,##0.00").format(v / 1e6) + " mi" : a >= 1000 ? df("#,##0").format(v) : df("#,##0.00").format(v);
        return "R$ " + n;
    }

    /** Variação do dia: ▲ 1,31% (ou "—" sem cotação). */
    public static String dayPct(Double p) { return WidgetData.change(p); }

    /** Variação do dia em reais, com sinal: +R$ 320 · −R$ 36,95. */
    public static String dayMoney(double v) { return (v >= 0 ? "+" : "−") + money(Math.abs(v)); }

    /** Variação total desde o início: +43,0% (valor atual ÷ aportado − 1). */
    public static String total(double v, double ap) {
        if (!(ap > 0)) return "";
        double p = (v / ap - 1) * 100;
        return (p >= 0 ? "+" : "−") + df("0.0").format(Math.abs(p)) + "%";
    }

    /** Nº de ações: 1.234. */
    public static String qty(long q) { return df("#,##0").format(q); }

    /** Aviso embaixo das posições: "+ 12 empresas · R$ 237 no CDB". */
    public static String rest(Row r) {
        int more = Math.max(0, r.np - r.pos.size());
        String a = more > 0 ? "+ " + more + (more == 1 ? " empresa" : " empresas") : "";
        String b = r.cash >= 0.01 ? money(r.cash) + " no CDB" : "";
        return a.isEmpty() ? b : b.isEmpty() ? a : a + " · " + b;
    }
}
