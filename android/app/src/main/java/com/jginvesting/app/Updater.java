package com.jginvesting.app;

import android.app.Activity;
import android.app.AlertDialog;
import android.content.Context;
import android.content.Intent;
import android.content.SharedPreferences;
import android.net.Uri;
import android.os.Build;
import android.provider.Settings;
import android.widget.Toast;

import java.io.File;
import java.io.FileOutputStream;
import java.io.InputStream;
import java.io.OutputStream;
import java.net.HttpURLConnection;
import java.net.URL;
import java.security.MessageDigest;

/** Oferta de nova versão: confere /app/version.json, pergunta (Atualizar / Depois), baixa, confere o SHA-256 e abre o instalador. */
final class Updater {
    private final Activity a;
    private UpdateLogic.Info pending;  // aguardando a permissão "instalar apps desta fonte"
    private boolean busy;

    Updater(Activity a) { this.a = a; }
    private SharedPreferences sp() { return a.getSharedPreferences("upd", Context.MODE_PRIVATE); }

    /** Ao abrir/voltar ao app: no máximo a cada 3 h. Se a permissão acabou de ser dada, segue com a atualização. */
    void onResume() {
        if (pending != null && canInstall()) { UpdateLogic.Info i = pending; pending = null; download(i); return; }
        long now = System.currentTimeMillis();
        if (busy || !UpdateLogic.shouldCheck(sp().getLong("last", 0), now)) return;
        sp().edit().putLong("last", now).apply();
        new Thread(() -> {
            String j = get(BuildConfig.SITE + "/app/version.json");
            UpdateLogic.Info i = j == null ? null : UpdateLogic.parse(j);
            if (UpdateLogic.offer(i, BuildConfig.VERSION_CODE, sp().getInt("snoozeCode", 0), sp().getLong("snoozeUntil", 0), System.currentTimeMillis()))
                a.runOnUiThread(() -> ask(i));
        }).start();
    }

    private void ask(UpdateLogic.Info i) {
        if (a.isFinishing()) return;
        new AlertDialog.Builder(a, AlertDialog.THEME_DEVICE_DEFAULT_DARK)
                .setTitle("Nova versão disponível (" + i.name + ")")
                .setMessage("Instalada: " + BuildConfig.VERSION_NAME + ".")
                .setPositiveButton("Atualizar", (d, w) -> start(i))
                .setNegativeButton("Depois", (d, w) -> sp().edit().putInt("snoozeCode", i.code)
                        .putLong("snoozeUntil", System.currentTimeMillis() + UpdateLogic.SNOOZE).apply())
                .show();
    }

    private boolean canInstall() { return Build.VERSION.SDK_INT < 26 || a.getPackageManager().canRequestPackageInstalls(); }

    private void start(UpdateLogic.Info i) {
        if (canInstall()) { download(i); return; }
        pending = i;  // Android 8+: o usuário libera "instalar apps desconhecidos" para este app uma vez
        new AlertDialog.Builder(a, AlertDialog.THEME_DEVICE_DEFAULT_DARK)
                .setTitle("Permitir a atualização")
                .setMessage("Na próxima tela, ative \"Permitir desta fonte\" para o JG Investing e volte ao app.")
                .setPositiveButton("Abrir ajustes", (d, w) -> {
                    try { a.startActivity(new Intent(Settings.ACTION_MANAGE_UNKNOWN_APP_SOURCES, Uri.parse("package:" + a.getPackageName()))); }
                    catch (Exception e) { pending = null; }
                })
                .setNegativeButton("Depois", (d, w) -> pending = null)
                .show();
    }

    private void download(UpdateLogic.Info i) {
        busy = true;
        Toast.makeText(a, "Baixando a versão " + i.name + "…", Toast.LENGTH_SHORT).show();
        new Thread(() -> {
            File f = ApkProvider.file(a);
            boolean ok = false;
            HttpURLConnection c = null;
            try {
                f.getParentFile().mkdirs();
                c = (HttpURLConnection) new URL(BuildConfig.SITE + i.apk).openConnection();
                c.setConnectTimeout(30000); c.setReadTimeout(60000);
                MessageDigest md = MessageDigest.getInstance("SHA-256");
                try (InputStream in = c.getInputStream(); OutputStream out = new FileOutputStream(f)) {
                    byte[] buf = new byte[16384]; int n;
                    while ((n = in.read(buf)) > 0) { out.write(buf, 0, n); md.update(buf, 0, n); }
                }
                ok = c.getResponseCode() == 200 && UpdateLogic.hex(md.digest()).equals(i.sha256);
            } catch (Exception e) { ok = false; }
            finally { if (c != null) c.disconnect(); }
            final boolean fine = ok;
            a.runOnUiThread(() -> {
                busy = false;
                if (!fine) { f.delete(); Toast.makeText(a, "Não foi possível baixar a atualização. Tente de novo mais tarde.", Toast.LENGTH_LONG).show(); return; }
                Intent in = new Intent(Intent.ACTION_VIEW).setDataAndType(ApkProvider.uri(a), ApkProvider.MIME)
                        .addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION | Intent.FLAG_ACTIVITY_NEW_TASK);
                try { a.startActivity(in); }  // instalador do sistema: o usuário confirma
                catch (Exception e) { Toast.makeText(a, "Instalador não encontrado.", Toast.LENGTH_LONG).show(); }
            });
        }).start();
    }

    private static String get(String url) {
        HttpURLConnection c = null;
        try {
            c = (HttpURLConnection) new URL(url).openConnection();
            c.setConnectTimeout(15000); c.setReadTimeout(15000);
            if (c.getResponseCode() != 200) return null;
            try (InputStream in = c.getInputStream()) {
                java.io.ByteArrayOutputStream b = new java.io.ByteArrayOutputStream(); byte[] buf = new byte[4096]; int n;
                while ((n = in.read(buf)) > 0) b.write(buf, 0, n);
                return b.toString("UTF-8");
            }
        } catch (Exception e) { return null; }
        finally { if (c != null) c.disconnect(); }
    }
}
