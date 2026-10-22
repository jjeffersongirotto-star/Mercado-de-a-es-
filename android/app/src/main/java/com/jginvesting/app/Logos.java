package com.jginvesting.app;

import android.content.Context;
import android.content.SharedPreferences;
import android.graphics.Bitmap;
import android.graphics.BitmapFactory;
import android.util.LruCache;

import java.io.File;
import java.io.FileOutputStream;
import java.util.Arrays;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

/** Logos das empresas guardados no aparelho (files/logos/<hash>.png). O nome é o hash do conteúdo: baixado uma vez, não muda;
 *  o widget não baixa de novo a cada 30 min. Guarda no máximo MAX arquivos (apaga os menos usados). */
final class Logos {
    private Logos() { }
    static final int MAX = 300;
    /** 1.23: logo que o servidor não tem só é pedido de novo depois disso (antes, a cada atualização, gastando o prazo do broadcast). */
    static final long FAIL_RETRY_MS = 24 * 3600_000L;
    /** 1.23: data de uso do arquivo (para apagar os menos usados) gravada no máximo uma vez por dia, não a cada desenho. */
    static final long TOUCH_MS = 24 * 3600_000L;

    static File dir(Context c) { File d = new File(c.getFilesDir(), "logos"); d.mkdirs(); return d; }

    private static SharedPreferences fails(Context c) { return c.getSharedPreferences("logos_fail", Context.MODE_PRIVATE); }

    /** Baixa os que faltam até deadline (ms do relógio). true = baixou algum. Fora da thread principal. */
    static boolean ensure(Context c, List<String> files, long deadline) {
        boolean got = false;
        File d = dir(c);
        SharedPreferences fp = fails(c); SharedPreferences.Editor fe = null; java.util.Set<String> failed = new java.util.HashSet<>();
        for (String f : files) {
            File x = new File(d, f);
            if (x.exists()) continue;
            long now = System.currentTimeMillis();
            if (WidgetData.within(fp.getLong(f, 0), now, FAIL_RETRY_MS)) continue;  // o servidor não tinha há menos de um dia
            int t = WidgetData.budget(deadline, now, 8000, 1000);
            if (t == 0) break;
            byte[] b = Api.logo(f, t);
            if (b == Api.MISSING) { if (fe == null) fe = fp.edit(); fe.putLong(f, now); failed.add(f); continue; }
            if (b == null) continue;  // sem internet / prazo: tenta na próxima atualização
            File tmp = new File(d, f + ".tmp");
            try (FileOutputStream o = new FileOutputStream(tmp)) { o.write(b); } catch (Exception e) { tmp.delete(); continue; }
            got |= tmp.renameTo(x);
        }
        if (fe != null) {  // as falhas vencidas saem (a lista não cresce sem limite)
            long now = System.currentTimeMillis();
            for (Map.Entry<String, ?> e : fp.getAll().entrySet())
                if (!failed.contains(e.getKey()) && (!(e.getValue() instanceof Long) || !WidgetData.within((Long) e.getValue(), now, FAIL_RETRY_MS))) fe.remove(e.getKey());
            fe.apply();
        }
        prune(d);
        return got;
    }

    private static void prune(File d) {
        File[] all = d.listFiles((dir, n) -> n.endsWith(".png"));
        if (all == null || all.length <= MAX) return;
        Arrays.sort(all, (a, b) -> Long.compare(a.lastModified(), b.lastModified()));
        for (int i = 0; i < all.length - MAX; i++) all[i].delete();
    }

    /** 1.23: logos já decodificados e no tamanho, entre um desenho e outro (até ~4 MB). O desenho também guarda os que usou no
     *  mapa dele (render): o MESMO objeto Bitmap em todas as versões de altura, que o Android manda uma vez só. */
    private static final LruCache<String, Bitmap> MEM = new LruCache<String, Bitmap>(4 * 1024 * 1024) {
        @Override protected int sizeOf(String k, Bitmap b) { return b.getAllocationByteCount(); }
    };
    private static final Map<String, Long> TOUCHED = new HashMap<>();

    /** Bitmap do logo em px×px (ARGB, ~px²×4 bytes) ou null. render = mesmo Bitmap para o mesmo arquivo num desenho. */
    static Bitmap bitmap(Context c, String f, int px, Map<String, Bitmap> render) {
        if (f == null) return null;
        String k = f + "@" + px;
        if (render != null && render.containsKey(k)) return render.get(k);
        File x = new File(dir(c), f);
        Bitmap out = MEM.get(k);
        if (out == null && x.exists()) {
            Bitmap b = BitmapFactory.decodeFile(x.getPath());
            if (b != null) { out = b.getWidth() == px && b.getHeight() == px ? b : Bitmap.createScaledBitmap(b, px, px, true); MEM.put(k, out); }
        }
        if (out != null) touch(x);
        if (render != null) render.put(k, out);
        return out;
    }

    private static void touch(File x) {
        long now = System.currentTimeMillis();
        synchronized (TOUCHED) {
            Long t = TOUCHED.get(x.getName());
            if (t != null && WidgetData.within(t, now, TOUCH_MS)) return;
            TOUCHED.put(x.getName(), now);
        }
        if (!WidgetData.within(x.lastModified(), now, TOUCH_MS)) x.setLastModified(now);
    }

    /** Lado do bitmap: o slot tem 32dp (até 96 px), o arquivo tem 128 px; com muitas linhas, menor (orçamento de ~1 MB do widget). */
    static int px(Context c, int rows) { return WidgetData.logoPx(c.getResources().getDisplayMetrics().density, rows); }

    static Map<String, Bitmap> newCache() { return new HashMap<>(); }
}
