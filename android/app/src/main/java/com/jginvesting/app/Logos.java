package com.jginvesting.app;

import android.content.Context;
import android.graphics.Bitmap;
import android.graphics.BitmapFactory;

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

    static File dir(Context c) { File d = new File(c.getFilesDir(), "logos"); d.mkdirs(); return d; }

    /** Baixa os que faltam (até deadline, em ms do relógio; 0 = sem limite). true = baixou algum. Fora da thread principal. */
    static boolean ensure(Context c, List<String> files, long deadline) {
        boolean got = false;
        File d = dir(c);
        for (String f : files) {
            if (deadline > 0 && System.currentTimeMillis() > deadline) break;
            File x = new File(d, f);
            if (x.exists()) continue;
            byte[] b = Api.logo(f, 8000);
            if (b == null) continue;
            File tmp = new File(d, f + ".tmp");
            try (FileOutputStream o = new FileOutputStream(tmp)) { o.write(b); } catch (Exception e) { tmp.delete(); continue; }
            got |= tmp.renameTo(x);
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

    /** Bitmap do logo em px×px (ARGB, ~px²×4 bytes) ou null. cache = mesmo Bitmap para o mesmo arquivo num desenho. */
    static Bitmap bitmap(Context c, String f, int px, Map<String, Bitmap> cache) {
        if (f == null) return null;
        String k = f + "@" + px;
        if (cache != null && cache.containsKey(k)) return cache.get(k);
        Bitmap out = null;
        File x = new File(dir(c), f);
        if (x.exists()) {
            Bitmap b = BitmapFactory.decodeFile(x.getPath());
            if (b != null) {
                out = b.getWidth() == px && b.getHeight() == px ? b : Bitmap.createScaledBitmap(b, px, px, true);
                x.setLastModified(System.currentTimeMillis());
            }
        }
        if (cache != null) cache.put(k, out);
        return out;
    }

    /** Lado do bitmap: o slot tem 32dp, mas o arquivo tem 64 px; com muitas linhas, menor (orçamento de ~1 MB do widget). */
    static int px(Context c, int rows) { return WidgetData.logoPx(c.getResources().getDisplayMetrics().density, rows); }

    static Map<String, Bitmap> newCache() { return new HashMap<>(); }
}
