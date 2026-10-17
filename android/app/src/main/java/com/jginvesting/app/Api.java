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
        try { return get("/api/widget?v=2&t=" + URLEncoder.encode(WidgetData.param(favs), "UTF-8"), timeoutMs); }
        catch (Exception e) { return null; }
    }

    /** Gráfico de 5 anos de uma ação (/api/widget/chart). */
    static String chart(String t, int timeoutMs) { try { return get("/api/widget/chart?t=" + URLEncoder.encode(t, "UTF-8"), timeoutMs); } catch (java.io.UnsupportedEncodingException e) { return null; } }

    /** ⟳ do widget: POST /api/refresh?src=widget (o servidor só refaz com dados velhos no pregão) -> JSON {started, refreshing} ou null. */
    static String refresh(int timeoutMs) { return req("/api/refresh?src=widget", timeoutMs, true); }

    /** Estado da atualização do servidor (/api/status, leve) -> JSON ou null. */
    static String status(int timeoutMs) { return get("/api/status", timeoutMs); }

    /** PNG de um logo (/logos/<arquivo>) ou null. */
    static byte[] logo(String file, int timeoutMs) {
        HttpURLConnection c = null;
        try {
            c = (HttpURLConnection) new URL(BuildConfig.SITE + "/logos/" + file).openConnection();
            c.setConnectTimeout(timeoutMs); c.setReadTimeout(timeoutMs);
            if (c.getResponseCode() != 200) return null;
            try (InputStream in = c.getInputStream()) {
                ByteArrayOutputStream b = new ByteArrayOutputStream(); byte[] buf = new byte[8192]; int n;
                while ((n = in.read(buf)) > 0 && b.size() < 200_000) b.write(buf, 0, n);
                byte[] x = b.toByteArray();
                return x.length > 8 && (x[0] & 0xff) == 0x89 && x[1] == 'P' ? x : null;
            }
        } catch (Exception e) {
            return null;
        } finally {
            if (c != null) c.disconnect();
        }
    }

    private static String get(String path, int timeoutMs) { return req(path, timeoutMs, false); }

    private static String req(String path, int timeoutMs, boolean post) {
        HttpURLConnection c = null;
        try {
            URL u = new URL(BuildConfig.SITE + path);
            c = (HttpURLConnection) u.openConnection();
            c.setConnectTimeout(timeoutMs); c.setReadTimeout(timeoutMs);
            if (post) { c.setRequestMethod("POST"); c.setDoOutput(true); c.setFixedLengthStreamingMode(0); c.getOutputStream().close(); }
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
