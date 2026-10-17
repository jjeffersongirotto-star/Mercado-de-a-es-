package com.jginvesting.app;

import org.json.JSONObject;

/** Regras da oferta de atualização (sem Android, testáveis na JVM). Versão publicada: /app/version.json do site. */
public final class UpdateLogic {
    private UpdateLogic() { }
    public static final long CHECK_EVERY = 3 * 3600_000L;   // confere no máximo a cada 3 h
    public static final long SNOOZE = 24 * 3600_000L;       // "Depois": um dia para a mesma versão

    public static final class Info {
        public final int code; public final String name, apk, sha256;
        Info(int code, String name, String apk, String sha256) { this.code = code; this.name = name; this.apk = apk; this.sha256 = sha256; }
    }

    /** version.json -> Info, ou null se faltar algo (sem oferta). */
    public static Info parse(String json) {
        try {
            JSONObject o = new JSONObject(json);
            int code = o.getInt("versionCode");
            String name = o.getString("versionName"), apk = o.getString("apk"), sha = o.getString("sha256").toLowerCase(java.util.Locale.ROOT);
            if (code <= 0 || !sha.matches("[0-9a-f]{64}") || !apk.startsWith("/")) return null;
            return new Info(code, name, apk, sha);
        } catch (Exception e) { return null; }
    }

    public static boolean shouldCheck(long lastCheck, long now) { return now - lastCheck >= CHECK_EVERY || now < lastCheck; }

    /** "Depois" vale só para a versão adiada e só até o prazo; versão mais nova aparece de novo. */
    public static boolean snoozed(int snoozeCode, long snoozeUntil, int code, long now) { return code == snoozeCode && now < snoozeUntil; }

    /** Oferece se a versão do site é mais nova que a instalada e não foi adiada. */
    public static boolean offer(Info i, int installed, int snoozeCode, long snoozeUntil, long now) {
        return i != null && i.code > installed && !snoozed(snoozeCode, snoozeUntil, i.code, now);
    }

    public static String hex(byte[] d) {
        StringBuilder b = new StringBuilder();
        for (byte x : d) b.append(String.format("%02x", x & 0xff));
        return b.toString();
    }
}
