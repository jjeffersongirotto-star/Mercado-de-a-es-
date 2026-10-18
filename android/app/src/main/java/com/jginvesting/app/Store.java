package com.jginvesting.app;

import android.content.Context;
import android.content.SharedPreferences;

/** O que o app guarda no aparelho: lista dos Favoritos (enviada pelo site) e a última resposta de /api/widget. */
final class Store {
    private Store() { }
    private static SharedPreferences sp(Context c) { return c.getSharedPreferences("jg", Context.MODE_PRIVATE); }

    static String favs(Context c) { return sp(c).getString("favs", "[]"); }
    /** -> true se a lista mudou. */
    static boolean setFavs(Context c, String json) {
        if (json.equals(favs(c))) return false;
        sp(c).edit().putString("favs", json).apply();
        return true;
    }
    /** Última resposta de /api/widget de cada lista ("fav" ou id do grupo). */
    static String data(Context c, String sel) { return sp(c).getString("data_" + sel, "{}"); }
    static void setData(Context c, String sel, String json) { sp(c).edit().putString("data_" + sel, json).apply(); }
    /** Guarda a resposta pedida em req (System.nanoTime no início do pedido) só se for mais nova que a guardada (WidgetData.accept). */
    static synchronized boolean setDataIfNewer(Context c, String sel, String json, long req) {
        if (!WidgetData.accept(req, sp(c).getLong("dreq_" + sel, Long.MIN_VALUE))) return false;
        sp(c).edit().putString("data_" + sel, json).putLong("dreq_" + sel, req).putLong("fat_" + sel, System.currentTimeMillis()).commit();  // hora em que os dados chegaram
        return true;
    }
    /** Quando a última resposta de /api/widget desta lista chegou (ms; 0 = nunca): é o horário que o widget mostra. */
    static long fetchedAt(Context c, String sel) { return sp(c).getLong("fat_" + sel, 0); }
    /** Grupos da aba Grupos enviados pelo site (grupos.js → pushGroups): [{id, n, t:[...]}]. */
    static String groups(Context c) { return sp(c).getString("groups", "[]"); }
    static boolean setGroups(Context c, String json) {
        if (json.equals(groups(c))) return false;
        sp(c).edit().putString("groups", json).apply();
        return true;
    }
    /** Atualização em andamento (⟳ ou troca de grupo): quando começou; 0 = parada. O widget mostra "Atualizando…" no lugar do horário. */
    static long loading(Context c) { return sp(c).getLong("loading", 0); }
    static void setLoading(Context c, long t) { sp(c).edit().putLong("loading", t).commit(); }
    /** Fim da atualização que começou em token: limpa só se ela ainda é a última (WidgetData.ownsLoading). true = limpou. */
    static synchronized boolean endLoading(Context c, long token) {
        if (!WidgetData.ownsLoading(token, loading(c))) return false;
        setLoading(c, 0); return true;
    }
    /** Lista escolhida em cada widget (padrão: Favoritos). */
    static String sel(Context c, int id) { return sp(c).getString("sel_" + id, "fav"); }
    static void setSel(Context c, int id, String sel) { sp(c).edit().putString("sel_" + id, sel).commit(); }
    /** Linha aberta (com o gráfico) e ponto marcado nela (-1 = último). */
    static String expanded(Context c) { return sp(c).getString("exp", ""); }
    static void setExpanded(Context c, String t) { sp(c).edit().putString("exp", t).putInt("zone", -1).commit(); }
    static int zone(Context c) { return sp(c).getInt("zone", -1); }
    static void setZone(Context c, int z) { sp(c).edit().putInt("zone", z).commit(); }
    /** Gráfico de 5 anos guardado por ação (resposta de /api/widget/chart) e quando foi buscado. */
    static String chart(Context c, String t) { return sp(c).getString("ch_" + t, null); }
    static long chartAt(Context c, String t) { return sp(c).getLong("cht_" + t, 0); }
    static void setChart(Context c, String t, String json) {
        SharedPreferences.Editor e = sp(c).edit();
        for (String k : sp(c).getAll().keySet()) if (k.startsWith("ch_") || k.startsWith("cht_")) e.remove(k);  // só o da ação aberta
        e.putString("ch_" + t, json).putLong("cht_" + t, System.currentTimeMillis()).apply();
    }

    // ---------- widget Grupo simulação (SimWidget) ----------
    /** Grupos de simulação enviados pelo site (grupos.js → pushSims): [{id, n, di, v0}]. -> true se mudaram. */
    static String sims(Context c) { return sp(c).getString("sims", "[]"); }
    static boolean setSims(Context c, String json) {
        if (json.equals(sims(c))) return false;
        sp(c).edit().putString("sims", json).apply();
        return true;
    }
    /** Grupo escolhido em cada widget Grupo simulação ("" = o primeiro). */
    static String simSel(Context c, int id) { return sp(c).getString("ssel_" + id, ""); }
    static void setSimSel(Context c, int id, String sel) { sp(c).edit().putString("ssel_" + id, sel).putString("sexp", "").commit(); }
    /** Última resposta de /api/widget/simgrupo por grupo (SimData.key) e quando chegou. */
    static String simData(Context c, String key) { return sp(c).getString("sd_" + key, "{}"); }
    static long simAt(Context c, String key) { return sp(c).getLong("sdt_" + key, 0); }
    static void setSimData(Context c, String key, String json) {
        SharedPreferences.Editor e = sp(c).edit();
        e.putString("sd_" + key, json).putLong("sdt_" + key, System.currentTimeMillis()).commit();
    }
    /** Respostas de grupos que não existem mais saem do aparelho. */
    static void pruneSims(Context c, java.util.Set<String> keep) {
        SharedPreferences.Editor e = sp(c).edit(); boolean ch = false;
        for (String k : sp(c).getAll().keySet())
            if ((k.startsWith("sd_") && !keep.contains(k.substring(3))) || (k.startsWith("sdt_") && !keep.contains(k.substring(4)))) { e.remove(k); ch = true; }
        if (ch) e.apply();
    }
    /** Modelo aberto (lista de posições) no widget Grupo simulação: "grupo|modelo" ou "". */
    static String simExp(Context c) { return sp(c).getString("sexp", ""); }
    static void setSimExp(Context c, String v) { sp(c).edit().putString("sexp", v).commit(); }
    /** "Atualizando…" do widget Grupo simulação. */
    static long simLoading(Context c) { return sp(c).getLong("sload", 0); }
    static void setSimLoading(Context c, long t) { sp(c).edit().putLong("sload", t).commit(); }
}
