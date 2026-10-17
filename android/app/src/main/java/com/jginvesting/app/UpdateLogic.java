package com.jginvesting.app;

import org.json.JSONObject;

/** Regras da oferta de atualização (sem Android, testáveis na JVM). Versão publicada: /app/version.json do site.
 *  Até a 1.2 a conferência valia por 3 h e contava mesmo sem resposta: aberto na instalação, o app só voltava a olhar 3 h depois.
 *  1.4–1.13: conferia ao abrir e ao voltar ao app no máximo a cada 10 min, contando também as conferências do widget (30 min e cada ⟳),
 *  e "Depois" valia 24 h (gravado): aberto logo depois de uma conferência (por exemplo durante a publicação), o app não oferecia nada.
 *  1.14: o app confere SEMPRE ao abrir e ao voltar (só junta aberturas seguidas em OPEN_GAP), sem cache, e "Depois" vale só enquanto
 *  o app fica aberto (SNOOZE, na memória). O widget continua no máximo a cada 10 min. */
public final class UpdateLogic {
    private UpdateLogic() { }
    public static final long CHECK_EVERY = 10 * 60_000L;     // depois de uma conferência que deu certo
    public static final long[] RETRY_MS = {0, 5_000L, 20_000L, 60_000L};  // na mesma abertura, se falhar (servidor acordando, rede)
    public static final long SNOOZE = 10 * 60_000L;         // "Depois": 10 min para a mesma versão, só na memória (abrir de novo o app oferece)
    public static final long OPEN_GAP = 15_000L;            // ao abrir/voltar: junta conferências seguidas (troca rápida de app)

    public static final class Info {
        public final int code; public final String name, apk, sha256;
        Info(int code, String name, String apk, String sha256) { this.code = code; this.name = name; this.apk = apk; this.sha256 = sha256; }
    }

    /** version.json -> Info, ou null se faltar algo (sem oferta). Formato igual desde a 1.2 (a 1.2 continua lendo). */
    public static Info parse(String json) {
        try {
            JSONObject o = new JSONObject(json);
            int code = o.getInt("versionCode");
            String name = o.getString("versionName"), apk = o.getString("apk"), sha = o.getString("sha256").toLowerCase(java.util.Locale.ROOT);
            if (code <= 0 || !sha.matches("[0-9a-f]{64}") || !apk.startsWith("/")) return null;
            return new Info(code, name, apk, sha);
        } catch (Exception e) { return null; }
    }

    /** lastOk = última conferência que recebeu um version.json válido. */
    public static boolean shouldCheck(long lastOk, long now, long every) { return now - lastOk >= every || now < lastOk; }
    public static boolean shouldCheck(long lastOk, long now) { return shouldCheck(lastOk, now, CHECK_EVERY); }

    /** Falha (sem resposta, resposta inválida) não conta como conferência feita. */
    public static long afterCheck(long lastOk, Info got, long now) { return got != null ? now : lastOk; }

    /** "Depois" vale só para a versão adiada e só até o prazo; versão mais nova aparece de novo. */
    public static boolean snoozed(int snoozeCode, long snoozeUntil, int code, long now) { return code == snoozeCode && now < snoozeUntil; }

    /** Compara nomes de versão por número em cada parte ("1.10" > "1.9", "1.13" > "1.9", "2" > "1.99"); nunca como texto. */
    public static int cmpName(String a, String b) {
        String[] x = a == null ? new String[0] : a.trim().split("\\."), y = b == null ? new String[0] : b.trim().split("\\.");
        for (int k = 0; k < Math.max(x.length, y.length); k++) {
            long p = k < x.length ? num(x[k]) : 0, q = k < y.length ? num(y[k]) : 0;
            if (p != q) return p < q ? -1 : 1;
        }
        return 0;
    }
    private static long num(String s) { String d = s.replaceAll("^\\D*(\\d*).*$", "$1"); try { return d.isEmpty() ? 0 : Long.parseLong(d); } catch (NumberFormatException e) { return 0; } }

    /** Mais nova que a instalada: versionCode maior (regra principal); mesmo versionCode com nome maior também conta (código esquecido). */
    public static boolean newer(Info i, int code, String name) { return i != null && (i.code > code || (i.code == code && name != null && cmpName(i.name, name) > 0)); }

    /** Oferece se a versão do site é mais nova que a instalada e não foi adiada. */
    public static boolean offer(Info i, int installed, String name, int snoozeCode, long snoozeUntil, long now) {
        return newer(i, installed, name) && !snoozed(snoozeCode, snoozeUntil, i.code, now);
    }
    public static boolean offer(Info i, int installed, int snoozeCode, long snoozeUntil, long now) { return offer(i, installed, null, snoozeCode, snoozeUntil, now); }

    /** Há versão mais nova conhecida (aviso no widget; vale mesmo com "Depois"). */
    public static boolean available(Info i, int installed, String name) { return newer(i, installed, name); }
    public static boolean available(Info i, int installed) { return newer(i, installed, null); }

    /** Ao abrir/voltar ao app: confere sempre (só junta aberturas a menos de OPEN_GAP da última tentativa). */
    public static boolean openCheck(long lastTry, long now) { return lastTry <= 0 || now - lastTry >= OPEN_GAP || now < lastTry; }

    /** Endereço sem cache no caminho (CDN/proxy): ?t= muda a cada conferência. */
    public static String url(String site, long now) { return site + "/app/version.json?t=" + now; }

    public static String hex(byte[] d) {
        StringBuilder b = new StringBuilder();
        for (byte x : d) b.append(String.format("%02x", x & 0xff));
        return b.toString();
    }
}
