package com.jginvesting.app;

import android.content.Context;
import android.content.SharedPreferences;

import java.io.File;
import java.io.FileInputStream;
import java.io.FileOutputStream;
import java.nio.charset.StandardCharsets;
import java.util.Arrays;
import java.util.HashSet;
import java.util.Map;
import java.util.Set;

/** O que o app guarda no aparelho: lista dos Favoritos (enviada pelo site) e a última resposta de /api/widget.
 *  1.23: as respostas grandes (/api/widget de cada lista, /api/widget/simgrupo de cada grupo, gráficos de 5 anos) ficam em arquivos
 *  (files/wdata e files/charts), fora do SharedPreferences, que o Android lê inteiro na memória e regrava a cada mudança;
 *  no SharedPreferences ficam só valores pequenos (seleções, horários, contadores). */
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

    // ---------- arquivos das respostas grandes ----------
    private static volatile boolean migrated;

    /** 1.23: na primeira leitura, as respostas que estavam no SharedPreferences (data_, sd_) vão para arquivos; gráficos antigos
     *  (ch_, cht_) e o número de pedido antigo (dreq_, nanoTime) saem. Uma vez por aparelho (marca "blobs1"). */
    private static synchronized void migrate(Context c) {
        if (migrated) return;
        SharedPreferences p = sp(c);
        if (!p.getBoolean("blobs1", false)) {
            SharedPreferences.Editor e = p.edit();
            for (Map.Entry<String, ?> en : p.getAll().entrySet()) {
                String k = en.getKey(); Object v = en.getValue();
                if (k.startsWith("data_")) { if (v instanceof String) writeBlob(c, dataFile(k.substring(5)), (String) v); e.remove(k); }
                else if (k.startsWith("sd_")) { if (v instanceof String) writeBlob(c, simFile(k.substring(3)), (String) v); e.remove(k); }
                else if (k.startsWith("ch_") || k.startsWith("cht_") || k.startsWith("dreq_")) e.remove(k);
            }
            e.putBoolean("blobs1", true).commit();
        }
        migrated = true;
    }

    private static File blobDir(Context c) { File d = new File(c.getFilesDir(), "wdata"); d.mkdirs(); return d; }
    private static String dataFile(String sel) { return "data_" + WidgetData.fileKey(sel); }
    private static String simFile(String key) { return "sd_" + WidgetData.fileKey(key); }

    private static String read(File f, String def) {
        if (!f.exists()) return def;
        try (FileInputStream in = new FileInputStream(f)) {
            java.io.ByteArrayOutputStream b = new java.io.ByteArrayOutputStream(); byte[] buf = new byte[16384]; int n;
            while ((n = in.read(buf)) > 0) b.write(buf, 0, n);
            return b.toString(StandardCharsets.UTF_8.name());
        } catch (Exception e) { return def; }
    }

    /** Grava inteiro (arquivo temporário + renomear): quem lê ao mesmo tempo vê o antigo ou o novo, nunca metade. */
    private static boolean write(File f, String text) {
        File tmp = new File(f.getPath() + ".tmp");
        try (FileOutputStream o = new FileOutputStream(tmp)) { o.write(text.getBytes(StandardCharsets.UTF_8)); }
        catch (Exception e) { tmp.delete(); return false; }
        return tmp.renameTo(f);
    }

    private static String readBlob(Context c, String name, String def) { migrate(c); return read(new File(blobDir(c), name), def); }
    private static void writeBlob(Context c, String name, String text) { write(new File(blobDir(c), name), text); }

    /** Apaga os arquivos com o prefixo que não estão em keep (nomes já com o prefixo). */
    private static void pruneBlobs(Context c, String prefix, Set<String> keep) {
        File[] fs = blobDir(c).listFiles((d, n) -> n.startsWith(prefix));
        if (fs != null) for (File f : fs) if (!keep.contains(f.getName())) f.delete();
    }

    /** Apaga do SharedPreferences as chaves prefixo + sufixo cujo sufixo não está em keep. */
    private static void prunePrefs(Context c, Set<String> keep, String... prefixes) {
        SharedPreferences.Editor e = sp(c).edit(); boolean ch = false;
        for (String k : sp(c).getAll().keySet())
            for (String p : prefixes) if (k.startsWith(p) && !keep.contains(k.substring(p.length()))) { e.remove(k); ch = true; break; }
        if (ch) e.apply();
    }

    // ---------- widget Favoritos (FavWidget) ----------
    /** Última resposta de /api/widget de cada lista ("fav" ou id do grupo). */
    static String data(Context c, String sel) { return readBlob(c, dataFile(sel), "{}"); }
    /** Número do próximo pedido de dados: contador guardado no aparelho, que só sobe (1.22: antes era System.nanoTime, que volta a
     *  zero quando o celular reinicia — depois disso toda resposta parecia antiga e o widget ficava parado no último horário). */
    static synchronized long nextReq(Context c) {
        long n = sp(c).getLong("reqseq", 0) + 1;
        sp(c).edit().putLong("reqseq", n).commit();
        return n;
    }
    /** Guarda a resposta pedida em req (Store.nextReq no início do pedido) só se for mais nova que a guardada (WidgetData.accept).
     *  Chave "dseq_" nova na 1.22: o "dreq_" antigo (nanoTime) é ignorado, então quem ficou preso destrava na 1ª atualização. */
    static synchronized boolean setDataIfNewer(Context c, String sel, String json, long req) {
        if (!WidgetData.accept(req, sp(c).getLong("dseq_" + sel, Long.MIN_VALUE))) return false;
        writeBlob(c, dataFile(sel), json);
        sp(c).edit().putLong("dseq_" + sel, req).remove("dreq_" + sel).putLong("fat_" + sel, System.currentTimeMillis()).commit();  // hora em que os dados chegaram
        return true;
    }
    /** Quando a última resposta de /api/widget desta lista chegou (ms; 0 = nunca): é o horário que o widget mostra. */
    static long fetchedAt(Context c, String sel) { return sp(c).getLong("fat_" + sel, 0); }
    /** Grupos da aba Grupos enviados pelo site (grupos.js → pushGroups): [{id, n, t:[...]}]. */
    static String groups(Context c) { return sp(c).getString("groups", "[]"); }
    /** -> true se mudaram. 1.23: as respostas guardadas de grupos que não existem mais saem do aparelho (arquivo e chaves). */
    static synchronized boolean setGroups(Context c, String json) {
        if (json.equals(groups(c))) return false;
        sp(c).edit().putString("groups", json).apply();
        Set<String> keep = new HashSet<>(); keep.add(WidgetData.FAV);
        for (WidgetData.Group g : WidgetData.groups(json)) keep.add(g.id);
        Set<String> files = new HashSet<>(); for (String s : keep) files.add(dataFile(s));
        migrate(c);
        pruneBlobs(c, "data_", files);
        prunePrefs(c, keep, "dseq_", "fat_", "dreq_");
        return true;
    }
    /** Atualização em andamento (⟳ ou troca de grupo): quando começou; 0 = parada. O widget mostra "Atualizando…" no lugar do horário. */
    static long loading(Context c) { return sp(c).getLong("loading", 0); }
    static void setLoading(Context c, long t) { sp(c).edit().putLong("loading", t).commit(); }
    /** Começa um "Atualizando…" (WidgetData.nextToken) e devolve a marca dele. */
    static synchronized long startLoading(Context c) {
        long tk = WidgetData.nextToken(loading(c), System.currentTimeMillis());
        setLoading(c, tk); return tk;
    }
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

    // ---------- gráficos de 5 anos (files/charts/<ticker>.json; horário = data do arquivo) ----------
    /** 1.23: guarda os CHART_MAX últimos (antes só o da ação aberta: abrir outra e voltar buscava de novo). */
    static final int CHART_MAX = 4;
    private static File chartFile(Context c, String t) {
        if (!WidgetData.validTicker(t)) return null;
        File d = new File(c.getFilesDir(), "charts"); d.mkdirs();
        return new File(d, t + ".json");
    }
    /** Gráfico de 5 anos guardado por ação (resposta de /api/widget/chart) e quando foi buscado. */
    static String chart(Context c, String t) { migrate(c); File f = chartFile(c, t); return f == null ? null : read(f, null); }
    static long chartAt(Context c, String t) { File f = chartFile(c, t); return f == null || !f.exists() ? 0 : f.lastModified(); }
    static synchronized void setChart(Context c, String t, String json) {
        migrate(c);
        File f = chartFile(c, t);
        if (f == null || !write(f, json)) return;
        f.setLastModified(System.currentTimeMillis());
        File[] all = f.getParentFile().listFiles((d, n) -> n.endsWith(".json"));
        if (all == null || all.length <= CHART_MAX) return;
        Arrays.sort(all, (a, b) -> Long.compare(b.lastModified(), a.lastModified()));
        for (int i = CHART_MAX; i < all.length; i++) if (!all[i].equals(f)) all[i].delete();
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
    static String simData(Context c, String key) { return readBlob(c, simFile(key), "{}"); }
    static long simAt(Context c, String key) { return sp(c).getLong("sdt_" + key, 0); }
    /** 1.23: como setDataIfNewer (mesmo contador nextReq, chave "sseq_"): resposta lenta de um pedido antigo não apaga a mais nova. */
    static synchronized boolean setSimDataIfNewer(Context c, String key, String json, long req) {
        if (!WidgetData.accept(req, sp(c).getLong("sseq_" + key, Long.MIN_VALUE))) return false;
        writeBlob(c, simFile(key), json);
        sp(c).edit().putLong("sseq_" + key, req).putLong("sdt_" + key, System.currentTimeMillis()).commit();
        return true;
    }
    /** Respostas de grupos que não existem mais saem do aparelho. */
    static synchronized void pruneSims(Context c, Set<String> keep) {
        Set<String> files = new HashSet<>(); for (String k : keep) files.add(simFile(k));
        migrate(c);
        pruneBlobs(c, "sd_", files);
        prunePrefs(c, keep, "sdt_", "sseq_");
    }
    /** Modelo aberto (lista de posições) no widget Grupo simulação: "grupo|modelo" ou "". */
    static String simExp(Context c) { return sp(c).getString("sexp", ""); }
    static void setSimExp(Context c, String v) { sp(c).edit().putString("sexp", v).commit(); }
    /** "Atualizando…" do widget Grupo simulação. */
    static long simLoading(Context c) { return sp(c).getLong("sload", 0); }
    static void setSimLoading(Context c, long t) { sp(c).edit().putLong("sload", t).commit(); }
    /** Fim do "Atualizando…" do Grupo simulação que começou em token (só se ainda é o último). */
    static synchronized void endSimLoading(Context c, long token) { if (WidgetData.ownsLoading(token, simLoading(c))) setSimLoading(c, 0); }
    static synchronized long startSimLoading(Context c) {
        long tk = WidgetData.nextToken(simLoading(c), System.currentTimeMillis());
        setSimLoading(c, tk); return tk;
    }

    // ---------- chaves por widget (sel_ID, ssel_ID) ----------
    /** 1.23: widget removido da tela inicial: a escolha dele sai do aparelho. */
    static void forgetWidgets(Context c, String prefix, int[] ids) {
        if (ids == null || ids.length == 0) return;
        SharedPreferences.Editor e = sp(c).edit();
        for (int id : ids) e.remove(prefix + id);
        e.apply();
    }
    /** 1.23: widgets restaurados (backup) com ids novos: a escolha de cada um passa para o id novo (WidgetData.remap). */
    static synchronized void remapWidgets(Context c, String prefix, int[] oldIds, int[] newIds) {
        Map<String, String> ch = WidgetData.remap(sp(c).getAll(), prefix, oldIds, newIds);
        if (ch.isEmpty()) return;
        SharedPreferences.Editor e = sp(c).edit();
        for (Map.Entry<String, String> x : ch.entrySet()) { if (x.getValue() == null) e.remove(x.getKey()); else e.putString(x.getKey(), x.getValue()); }
        e.commit();
    }
}
