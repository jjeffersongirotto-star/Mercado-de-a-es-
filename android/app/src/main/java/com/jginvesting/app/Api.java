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

    /** 1.23: timeoutMs de cada chamada é o tempo TOTAL dela (relógio), não por etapa: connect e read timeouts valem cada um o
     *  prazo inteiro e um servidor lento que manda aos poucos não para o read timeout; este vigia desliga a conexão no fim do prazo.
     *  Quem chama passa o que resta do prazo do broadcast (WidgetData.budget). */
    private static final java.util.concurrent.ScheduledThreadPoolExecutor WD = new java.util.concurrent.ScheduledThreadPoolExecutor(1, r -> {
        Thread t = new Thread(r, "jg-api-prazo"); t.setDaemon(true); return t;
    });
    static { WD.setRemoveOnCancelPolicy(true); }

    /** Desliga a conexão c depois de ms (cancelar no fim da chamada). */
    static java.util.concurrent.ScheduledFuture<?> watch(HttpURLConnection c, int ms) {
        return WD.schedule(c::disconnect, Math.max(1, ms), java.util.concurrent.TimeUnit.MILLISECONDS);
    }

    /** Logo que não existe no servidor (resposta diferente de 200 ou que não é PNG): Logos guarda e só tenta de novo depois de um dia. */
    static final byte[] MISSING = new byte[0];

    /** -> JSON da resposta ou null (sem internet, servidor acordando etc.). */
    static String widget(List<String> favs, int timeoutMs) {
        try { return get("/api/widget?v=2&t=" + URLEncoder.encode(WidgetData.param(favs), "UTF-8"), timeoutMs); }
        catch (Exception e) { return null; }
    }

    /** Widget Grupo simulação: por modelo, aportado, valor atual, variação do dia e maiores posições (/api/widget/simgrupo). */
    static String simgrupo(SimData.Sim s, int timeoutMs) { return get("/api/widget/simgrupo?" + SimData.query(s), timeoutMs); }

    /** Gráfico de 5 anos de uma ação (/api/widget/chart). */
    static String chart(String t, int timeoutMs) { try { return get("/api/widget/chart?t=" + URLEncoder.encode(t, "UTF-8"), timeoutMs); } catch (java.io.UnsupportedEncodingException e) { return null; } }

    /** ⟳ do widget: POST /api/refresh?src=widget (o servidor só refaz com dados velhos no pregão) -> JSON {started, refreshing} ou null. */
    static String refresh(int timeoutMs) { return req("/api/refresh?src=widget", timeoutMs, true); }

    /** Estado da atualização do servidor (/api/status, leve) -> JSON ou null. */
    static String status(int timeoutMs) { return get("/api/status", timeoutMs); }

    /** PNG de um logo (/logos/<arquivo>), MISSING (o servidor não tem) ou null (sem internet, prazo: tenta na próxima). */
    static byte[] logo(String file, int timeoutMs) {
        if (timeoutMs <= 0) return null;
        HttpURLConnection c = null; java.util.concurrent.ScheduledFuture<?> w = null;
        try {
            c = (HttpURLConnection) new URL(BuildConfig.SITE + "/logos/" + file).openConnection();
            c.setConnectTimeout(timeoutMs); c.setReadTimeout(timeoutMs);
            w = watch(c, timeoutMs);
            int code = c.getResponseCode();
            if (code != 200) return code >= 400 && code < 500 ? MISSING : null;  // 5xx: servidor acordando, tenta de novo
            try (InputStream in = c.getInputStream()) {
                ByteArrayOutputStream b = new ByteArrayOutputStream(); byte[] buf = new byte[8192]; int n;
                while ((n = in.read(buf)) > 0 && b.size() < 200_000) b.write(buf, 0, n);
                byte[] x = b.toByteArray();
                return x.length > 8 && (x[0] & 0xff) == 0x89 && x[1] == 'P' ? x : MISSING;
            }
        } catch (Exception e) {
            return null;
        } finally {
            if (w != null) w.cancel(false);
            if (c != null) c.disconnect();
        }
    }

    private static String get(String path, int timeoutMs) { return req(path, timeoutMs, false); }

    private static String req(String path, int timeoutMs, boolean post) {
        if (timeoutMs <= 0) return null;
        HttpURLConnection c = null; java.util.concurrent.ScheduledFuture<?> w = null;
        try {
            URL u = new URL(BuildConfig.SITE + path);
            c = (HttpURLConnection) u.openConnection();
            c.setConnectTimeout(timeoutMs); c.setReadTimeout(timeoutMs);
            w = watch(c, timeoutMs);
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
            if (w != null) w.cancel(false);
            if (c != null) c.disconnect();
        }
    }
}
