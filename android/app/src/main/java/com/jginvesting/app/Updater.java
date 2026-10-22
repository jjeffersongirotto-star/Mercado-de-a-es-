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
    private boolean busy, checking, resumed, force;
    private AlertDialog dialog;

    /** App aberto (para mostrar a oferta quando uma conferência de fora da abertura acha versão nova). */
    private static java.lang.ref.WeakReference<Updater> live = new java.lang.ref.WeakReference<>(null);

    Updater(Activity a) { this.a = a; live = new java.lang.ref.WeakReference<>(this); }
    static SharedPreferences sp(Context c) { return c.getSharedPreferences("upd", Context.MODE_PRIVATE); }
    private SharedPreferences sp() { return sp(a); }

    /** Última versão publicada que o app ou o widget viu (null se nenhuma). */
    static UpdateLogic.Info known(Context c) { return UpdateLogic.parse(sp(c).getString("known", "")); }
    static boolean available(Context c) { return UpdateLogic.available(known(c), BuildConfig.VERSION_CODE, BuildConfig.VERSION_NAME); }
    // conferência ao abrir e "Depois": só na memória do processo (abrir o app de novo depois de fechado oferece outra vez)
    private static long lastTry, snoozeUntil; private static int snoozeCode;

    /** Uma conferência (com novas tentativas se falhar). Guarda a versão vista; só conta como feita se deu certo. Fora da thread principal. */
    static UpdateLogic.Info fetch(Context c, int timeoutMs, int tries) {
        UpdateLogic.Info i = null;
        for (int k = 0; k < Math.min(tries, UpdateLogic.RETRY_MS.length) && i == null; k++) {
            if (UpdateLogic.RETRY_MS[k] > 0) try { Thread.sleep(UpdateLogic.RETRY_MS[k]); } catch (InterruptedException e) { break; }
            String j = get(UpdateLogic.url(BuildConfig.SITE, System.currentTimeMillis()), timeoutMs);
            i = j == null ? null : UpdateLogic.parse(j);
            if (i != null) sp(c).edit().putString("known", j).putLong("ok", System.currentTimeMillis()).commit();
        }
        return i;
    }

    /** 1.23: atômico (o widget, o app e a ponte do site conferem em threads diferentes; só uma passa em cada OPEN_GAP). */
    private static final java.util.concurrent.atomic.AtomicLong lastData = new java.util.concurrent.atomic.AtomicLong();

    /** 1.15: a cada atualização de dados (widget a cada 30 min e no ⟳, ⟳ e recarga automática do site dentro do app) também confere
     *  a versão, sem cache (?t= + no-cache; só junta conferências a menos de OPEN_GAP). Achou versão nova: aviso no widget e, com o app
     *  aberto na tela, a oferta (Atualizar / Depois) na hora. true = mudou o aviso. Fora da thread principal. */
    static boolean quietCheck(Context c, int timeoutMs) {
        long now = System.currentTimeMillis(), last = lastData.get();
        if (!UpdateLogic.dataCheck(last, now) || !lastData.compareAndSet(last, now)) return false;
        boolean before = available(c);
        UpdateLogic.Info i = fetch(c, timeoutMs, 1);
        Updater u = live.get();
        if (u != null && i != null) u.a.runOnUiThread(() -> u.maybeAsk(i));
        return before != available(c);
    }

    /** Mesmo que quietCheck, em segundo plano (ponte do site: JGApp.dataRefreshed); redesenha o widget se o aviso mudou. */
    static void dataCheckAsync(Context ctx) {
        final Context c = ctx.getApplicationContext();
        new Thread(() -> { if (quietCheck(c, 15000)) FavWidget.render(c); }).start();  // render protegido (1.23)
    }

    /** Ao abrir e ao voltar ao app. Se a permissão acabou de ser dada, segue com a atualização. */
    void onResume() {
        resumed = true;
        if (pending != null && canInstall()) { UpdateLogic.Info i = pending; pending = null; download(i); return; }
        maybeAsk(known(a));  // já se sabe de uma versão nova (widget ou conferência anterior): oferece na hora
        long now = System.currentTimeMillis();
        if (busy || checking || !(force || UpdateLogic.openCheck(lastTry, now))) return;  // sem a trava de 10 min do widget
        checking = true; lastTry = now;
        new Thread(() -> {
            UpdateLogic.Info i = null;
            try {
                boolean before = available(a);
                i = fetch(a, 20000, UpdateLogic.RETRY_MS.length);
                // 1.14 redesenhava o widget aqui sem proteção: um erro do widget (ex.: bitmaps grandes demais para o launcher) matava a
                // thread antes da oferta e deixava "checking" preso — nenhuma conferência mais até fechar o app; 1.23: render protegido
                if (before != available(a)) { FavWidget.render(a.getApplicationContext()); SimWidget.render(a.getApplicationContext()); }
            } finally {
                final UpdateLogic.Info got = i != null ? i : known(a);  // sem resposta agora: a última versão vista (widget ou antes)
                a.runOnUiThread(() -> { checking = false; maybeAsk(got); });
            }
        }).start();
    }

    void onPause() { resumed = false; }

    /** Toque em "Atualização disponível" no widget: oferece mesmo se adiada. */
    void forceOffer() { force = true; }

    private void maybeAsk(UpdateLogic.Info i) {
        if (i == null || !resumed || busy || a.isFinishing() || a.isDestroyed() || (dialog != null && dialog.isShowing())) return;
        boolean ok = force ? UpdateLogic.available(i, BuildConfig.VERSION_CODE, BuildConfig.VERSION_NAME)
                : UpdateLogic.offer(i, BuildConfig.VERSION_CODE, BuildConfig.VERSION_NAME, snoozeCode, snoozeUntil, System.currentTimeMillis());
        if (!ok) return;
        force = false;
        ask(i);
    }

    private void ask(UpdateLogic.Info i) {
        if (a.isFinishing()) return;
        dialog = new AlertDialog.Builder(a, AlertDialog.THEME_DEVICE_DEFAULT_DARK)
                .setTitle("Nova versão disponível (" + i.name + ")")
                .setMessage("Instalada: " + BuildConfig.VERSION_NAME + ".")
                .setPositiveButton("Atualizar", (d, w) -> start(i))
                .setNegativeButton("Depois", (d, w) -> { snoozeCode = i.code; snoozeUntil = System.currentTimeMillis() + UpdateLogic.SNOOZE; })
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

    private static String get(String url, int timeoutMs) {
        if (timeoutMs <= 0) return null;
        HttpURLConnection c = null; java.util.concurrent.ScheduledFuture<?> w = null;
        try {
            c = (HttpURLConnection) new URL(url).openConnection();
            c.setConnectTimeout(timeoutMs); c.setReadTimeout(timeoutMs);
            w = Api.watch(c, timeoutMs);  // prazo total (1.23)
            c.setUseCaches(false);
            c.setRequestProperty("Cache-Control", "no-cache"); c.setRequestProperty("Pragma", "no-cache");
            if (c.getResponseCode() != 200) return null;
            try (InputStream in = c.getInputStream()) {
                java.io.ByteArrayOutputStream b = new java.io.ByteArrayOutputStream(); byte[] buf = new byte[4096]; int n;
                while ((n = in.read(buf)) > 0) b.write(buf, 0, n);
                return b.toString("UTF-8");
            }
        } catch (Exception e) { return null; }
        finally { if (w != null) w.cancel(false); if (c != null) c.disconnect(); }
    }
}
