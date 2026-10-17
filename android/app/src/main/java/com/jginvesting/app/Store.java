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
    /** Grupos da aba Grupos enviados pelo site (grupos.js → pushGroups): [{id, n, t:[...]}]. */
    static String groups(Context c) { return sp(c).getString("groups", "[]"); }
    static boolean setGroups(Context c, String json) {
        if (json.equals(groups(c))) return false;
        sp(c).edit().putString("groups", json).apply();
        return true;
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
}
