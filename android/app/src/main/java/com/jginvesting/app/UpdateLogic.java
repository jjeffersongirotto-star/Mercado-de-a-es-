package com.jginvesting.app;

import org.json.JSONObject;

/** Regras da oferta de atualização (sem Android, testáveis na JVM). Versão publicada: /app/version.json do site.
 *  Até a 1.2 a conferência valia por 3 h e contava mesmo sem resposta: aberto na instalação, o app só voltava a olhar 3 h depois.
 *  Agora: confere ao abrir e ao voltar ao app (no máximo a cada 10 min), só conta a conferência que deu certo e tenta de novo na falha. */
public final class UpdateLogic {
    private UpdateLogic() { }
    public static final long CHECK_EVERY = 10 * 60_000L;     // depois de uma conferência que deu certo
    public static final long[] RETRY_MS = {0, 5_000L, 20_000L, 60_000L};  // na mesma abertura, se falhar (servidor acordando, rede)
    public static final long SNOOZE = 24 * 3600_000L;       // "Depois": um dia para a mesma versão

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

    /** Oferece se a versão do site é mais nova que a instalada e não foi adiada. */
    public static boolean offer(Info i, int installed, int snoozeCode, long snoozeUntil, long now) {
        return i != null && i.code > installed && !snoozed(snoozeCode, snoozeUntil, i.code, now);
    }

    /** Há versão mais nova conhecida (aviso no widget; vale mesmo com "Depois"). */
    public static boolean available(Info i, int installed) { return i != null && i.code > installed; }

    public static String hex(byte[] d) {
        StringBuilder b = new StringBuilder();
        for (byte x : d) b.append(String.format("%02x", x & 0xff));
        return b.toString();
    }
}
