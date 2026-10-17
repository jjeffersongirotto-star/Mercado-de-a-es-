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
    static String data(Context c) { return sp(c).getString("data", "{}"); }
    static void setData(Context c, String json) { sp(c).edit().putString("data", json).apply(); }
}
