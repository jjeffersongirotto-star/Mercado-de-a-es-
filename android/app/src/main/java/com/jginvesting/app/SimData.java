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

    /** Um grupo de simulação da aba Grupos: nome (= id), data inicial (AAAA-MM-DD; grupos antigos AAAA-MM), valor inicial e (1.17+) f = JSON {ap, ex, ret} com
     *  aporte mensal, aportes e retiradas extraordinários da Previsão ("" = grupo antigo, só o valor inicial). */
    public static final class Sim {
        public final String id, name, di, f; public final double v0;
        Sim(String id, String name, String di, double v0, String f) { this.id = id; this.name = name; this.di = di; this.v0 = v0; this.f = f; }
    }

    /** Uma posição de um modelo: ticker, nome popular (ou null), nº de ações, preço médio (1.20+; NaN sem dado), valor investido e valor atual. */
    public static final class Pos {
        public final String t, s; public final long q; public final double pm, inv, v;
        Pos(String t, String s, long q, double pm, double inv, double v) { this.t = t; this.s = s; this.q = q; this.pm = pm; this.inv = inv; this.v = v; }
    }

    /** Uma linha do widget: modelo, valor aportado, valor atual, variação do dia (R$ e %), caixa no CDB e as maiores posições. */
    public static final class Row {
        public final String m, n; public final double ap, v, dv, cash; public final Double dp; public final int np;
        public final List<Pos> pos = new ArrayList<>();
        /** CDB no período (servidor: modelos.grupo → cdb): total aplicado, rendimento recebido e parte aplicada do saldo de hoje (1.20+; 0 sem dado). */
        public double cdbAp, cdbJ, cdbP;
        Row(String m, String n, double ap, double v, double dv, Double dp, double cash, int np) {
            this.m = m; this.n = n; this.ap = ap; this.v = v; this.dv = dv; this.dp = dp; this.cash = cash; this.np = np;
        }
    }

    private static final String DI = "\\d{4}-\\d{2}(-\\d{2})?", MID = "[a-z0-9_]{1,24}";
    public static boolean validModel(String m) { return m != null && m.matches(MID); }

    /** JSON [{id, n, di, v0}] do site -> grupos válidos (nome até 80 letras, data AAAA-MM-DD ou, grupos antigos, AAAA-MM; valor > 0), sem repetir o id. */
    public static List<Sim> sims(String json) {
        List<Sim> out = new ArrayList<>();
        try {
            JSONArray a = new JSONArray(json);
            for (int i = 0; i < a.length() && out.size() < 30; i++) {
                JSONObject o = a.getJSONObject(i);
                String id = o.optString("id", ""), n = o.optString("n", id), di = o.optString("di", "");
                double v0 = o.optDouble("v0", 0);
                JSONObject fo = o.optJSONObject("f"); String f = fo == null ? "" : fo.toString();
                if (f.length() > 4000) f = "";
                if (id.isEmpty() || id.length() > 80 || !di.matches(DI) || !(v0 > 0)) continue;
                boolean dup = false; for (Sim s : out) if (s.id.equals(id)) dup = true;
                if (!dup) out.add(new Sim(id, n.isEmpty() ? id : n, di, v0, f));
            }
        } catch (Exception e) { /* sem grupos */ }
        return out;
    }

    /** Data inicial para o "Desde…" do widget: AAAA-MM-DD -> DD/MM/AAAA; AAAA-MM (grupos antigos) -> MM/AAAA. */
    public static String since(String di) {
        return di.length() >= 10 ? di.substring(8, 10) + "/" + di.substring(5, 7) + "/" + di.substring(0, 4) : di.substring(5) + "/" + di.substring(0, 4);
    }

    public static Sim find(String id, List<Sim> ss) { for (Sim s : ss) if (s.id.equals(id)) return s; return null; }

    /** Grupo escolhido no widget; o que sumiu (ou nenhum escolhido) = o primeiro; sem grupos = null. */
    public static Sim pick(String sel, List<Sim> ss) { Sim s = find(sel == null ? "" : sel, ss); return s != null ? s : ss.isEmpty() ? null : ss.get(0); }

    /** Chave da resposta guardada: muda quando a data ou o valor inicial do grupo mudam (resposta antiga não vale). */
    public static String key(Sim s) { return s == null ? "" : s.id + "|" + s.di + "|" + s.v0 + (s.f.isEmpty() ? "" : "|" + Integer.toHexString(s.f.hashCode())); }

    /** Parâmetros de /api/widget/simgrupo. */
    public static String query(Sim s) {
        try { return "di=" + java.net.URLEncoder.encode(s.di, "UTF-8") + "&v0=" + new DecimalFormat("0.##", DecimalFormatSymbols.getInstance(Locale.ROOT)).format(s.v0)
                + (s.f.isEmpty() ? "" : "&f=" + java.net.URLEncoder.encode(s.f, "UTF-8")); }
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
                    row.pos.add(new Pos(t, q.isNull("s") ? null : q.optString("s", null), q.optLong("q", 0), q.optDouble("pm", Double.NaN), q.optDouble("inv", 0), q.optDouble("v", 0)));
                }
                JSONObject cd = o.optJSONObject("cdb");
                if (cd != null) { row.cdbAp = cd.optDouble("ap", 0); row.cdbJ = cd.optDouble("j", 0); row.cdbP = cd.optDouble("p", 0); }
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

    /** Preço médio da posição: R$ 38,46 (sempre com centavos; "—" sem dado). */
    public static String price(double p) { return p > 0 ? "R$ " + df("#,##0.00").format(p) : "—"; }

    /** Linha Caixa no CDB: rendimento no período todo (juros ÷ tudo que já foi aplicado), "" sem dado. */
    public static String cdbPct(Row r) { return r.cdbAp > 0 ? total(r.cdbAp + r.cdbJ, r.cdbAp) : ""; }

    /** Nº de ações: 1.234. */
    public static String qty(long q) { return df("#,##0").format(q); }

    /** Uma linha da lista do widget: um modelo (ROW) e, logo abaixo do modelo aberto, o título das posições (HEAD), TODAS as empresas
     *  (POS, rolando dentro do widget) e o caixa no CDB no fim (CDB, só se houver). */
    public static final class Item {
        public static final int ROW = 0, HEAD = 1, POS = 2, CDB = 3;
        public final int type; public final Row row; public final Pos pos;
        Item(int type, Row row, Pos pos) { this.type = type; this.row = row; this.pos = pos; }
        public long id() { return ((long) row.m.hashCode() << 20) ^ (type == POS ? pos.t.hashCode() & 0xFFFFF : type); }
    }

    public static List<Item> items(List<Row> rows, String openModel) {
        List<Item> out = new ArrayList<>();
        for (Row r : rows) {
            out.add(new Item(Item.ROW, r, null));
            if (!r.m.equals(openModel)) continue;
            out.add(new Item(Item.HEAD, r, null));
            for (Pos p : r.pos) out.add(new Item(Item.POS, r, p));
            if (r.cash >= 0.01) out.add(new Item(Item.CDB, r, null));
        }
        return out;
    }

    /** Linha de baixo do título (10,5sp): altura fixa no Android 12+ para a conta das linhas inteiras fechar. */
    public static float subDp(float fontScale) { return 14 * Math.max(1f, fontScale); }

    /** Cabeçalho até a lista (dp): 8 em cima + barra 36 + linha "Desde…" + 4 + títulos (2 linhas, WidgetData.colsDp) + divisor 1 + 6 embaixo. */
    public static float headerDp(float fontScale, boolean sub) { return 8 + 36 + (sub ? subDp(fontScale) : 0) + 4 + WidgetData.colsDp(fontScale) + 1 + 6; }

    /** Altura de cada linha de modelo (px) para mostrar só linhas inteiras (como o Favoritos 1.12, WidgetData.rows): com todos fechados,
     *  N linhas que cabem esticadas até a borda (o resto rolando); com um modelo aberto, linha base (a lista rola até as posições). 0 = altura desconhecida. */
    public static int rowPx(int hDp, float density, float fontScale, boolean sub, int models, boolean anyOpen) {
        if (hDp <= 0) return 0;
        int listPx = Math.round((hDp - headerDp(fontScale, sub)) * density);
        int[] r = WidgetData.rows(listPx, density, fontScale, anyOpen ? 0 : models);
        return anyOpen ? Math.round(WidgetData.rowBaseDp(fontScale) * density) : r[1];
    }

    /** Nome do arquivo da planilha: "Grupo simulação 2026-10-18.xlsx" (sem / \\ : * ? " < > |). */
    public static String fileName(String name, String day) {
        String n = name == null ? "" : name.replaceAll("[\\\\/:*?\"<>|]", "-").trim();
        if (n.length() > 60) n = n.substring(0, 60).trim();
        return (n.isEmpty() ? "Grupo simulação" : n) + " " + day + ".xlsx";
    }

    /** " + R$ 500/mês" quando o grupo tem aporte mensal (1.17+), senão "". */
    public static String monthly(Sim s) {
        try { double ap = s.f.isEmpty() ? 0 : new JSONObject(s.f).optDouble("ap", 0); return ap > 0 ? " + " + money(ap) + "/mês" : ""; } catch (Exception e) { return ""; }
    }

    /** Largura da coluna Empresa (dp): só o necessário para o maior nome (ou ticker), entre 56 e 112 dp; nomes maiores quebram em 2 linhas. */
    public static int empDp(Row r) {
        int n = 4;
        for (Pos p : r.pos) { String s = p.s != null && !p.s.isEmpty() ? p.s : p.t; n = Math.max(n, Math.max(s.length(), (int) Math.ceil(p.t.length() * 0.85))); }
        return Math.max(56, Math.min(112, Math.round(n * 6.6f) + 6));
    }

    /** Título do modelo aberto: "Posições atuais · 30 empresas" ou "Tudo no CDB". */
    public static String head(Row r) { return r.np == 0 ? "Tudo no CDB" : "Posições atuais · " + r.np + (r.np == 1 ? " empresa" : " empresas"); }
}
