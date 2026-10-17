package com.jginvesting.app;

import java.io.ByteArrayOutputStream;
import java.io.InputStream;
import java.net.HttpURLConnection;
import java.net.URL;
import java.net.URLEncoder;
import java.nio.charset.StandardCharsets;
import java.util.List;

/** Consulta /api/widget do site (preço, variação e Barato/Caro só dos favoritos). */
final class Api {
    private Api() { }

    /** -> JSON da resposta ou null (sem internet, servidor acordando etc.). */
    static String widget(List<String> favs, int timeoutMs) {
        try { return get("/api/widget?t=" + URLEncoder.encode(WidgetData.param(favs), "UTF-8"), timeoutMs); }
        catch (Exception e) { return null; }
    }

    /** Gráfico de 5 anos de uma ação (/api/widget/chart). */
    static String chart(String t, int timeoutMs) { return get("/api/widget/chart?t=" + t, timeoutMs); }

    private static String get(String path, int timeoutMs) {
        HttpURLConnection c = null;
        try {
            URL u = new URL(BuildConfig.SITE + path);
            c = (HttpURLConnection) u.openConnection();
            c.setConnectTimeout(timeoutMs); c.setReadTimeout(timeoutMs);
            c.setRequestProperty("Accept", "application/json");
            if (c.getResponseCode() != 200) return null;
            try (InputStream in = c.getInputStream()) {
                ByteArrayOutputStream b = new ByteArrayOutputStream(); byte[] buf = new byte[8192]; int n;
                while ((n = in.read(buf)) > 0) b.write(buf, 0, n);
                return b.toString(StandardCharsets.UTF_8.name());
            }
        } catch (Exception e) {
            return null;
        } finally {
            if (c != null) c.disconnect();
        }
    }
}
