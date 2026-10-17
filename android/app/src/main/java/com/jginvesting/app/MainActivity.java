package com.jginvesting.app;

import android.annotation.SuppressLint;
import android.app.Activity;
import android.content.ActivityNotFoundException;
import android.content.ContentValues;
import android.content.Intent;
import android.graphics.Insets;
import android.net.Uri;
import android.os.Build;
import android.os.Bundle;
import android.os.Environment;
import android.provider.MediaStore;
import android.view.View;
import android.view.WindowInsets;
import android.webkit.JavascriptInterface;
import android.webkit.ValueCallback;
import android.webkit.WebChromeClient;
import android.webkit.WebResourceRequest;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.widget.FrameLayout;
import android.widget.Toast;

import java.io.File;
import java.io.FileOutputStream;
import java.io.OutputStream;
import java.nio.charset.StandardCharsets;

/** O site em tela cheia. A ponte window.JGApp recebe os Favoritos (widget) e grava os arquivos do Exportar. */
public class MainActivity extends Activity {
    private static final int REQ_FILE = 7;
    private WebView web;
    private ValueCallback<Uri[]> fileCb;
    private Updater updater;

    @SuppressLint({"SetJavaScriptEnabled", "AddJavascriptInterface"})
    @Override protected void onCreate(Bundle saved) {
        super.onCreate(saved);
        FrameLayout root = new FrameLayout(this);
        root.setBackgroundColor(getColor(R.color.theme));
        web = new WebView(this);
        root.addView(web, new FrameLayout.LayoutParams(-1, -1));
        setContentView(root);
        // Android 15+ desenha atrás das barras: afasta o site da barra de status, da de navegação e do teclado
        root.setOnApplyWindowInsetsListener((v, in) -> {
            if (Build.VERSION.SDK_INT >= 30) {
                Insets s = in.getInsets(WindowInsets.Type.systemBars() | WindowInsets.Type.ime() | WindowInsets.Type.displayCutout());
                v.setPadding(s.left, s.top, s.right, s.bottom);
            } else {
                v.setPadding(in.getSystemWindowInsetLeft(), in.getSystemWindowInsetTop(), in.getSystemWindowInsetRight(), in.getSystemWindowInsetBottom());
            }
            return in;
        });

        WebSettings s = web.getSettings();
        s.setJavaScriptEnabled(true);
        s.setDomStorageEnabled(true);
        s.setDatabaseEnabled(true);
        s.setUserAgentString(s.getUserAgentString() + " JGInvestingApp/" + BuildConfig.VERSION_NAME);
        web.addJavascriptInterface(new Bridge(), "JGApp");
        web.setWebViewClient(new WebViewClient() {
            @Override public boolean shouldOverrideUrlLoading(WebView v, WebResourceRequest r) {
                Uri u = r.getUrl();
                if (Uri.parse(BuildConfig.SITE).getHost().equals(u.getHost())) return false;
                try { startActivity(new Intent(Intent.ACTION_VIEW, u)); } catch (ActivityNotFoundException e) { /* sem app para abrir */ }
                return true;  // links de fora (notícias, RI) abrem no navegador
            }
        });
        web.setWebChromeClient(new WebChromeClient() {
            @Override public boolean onShowFileChooser(WebView v, ValueCallback<Uri[]> cb, FileChooserParams p) {
                if (fileCb != null) fileCb.onReceiveValue(null);
                fileCb = cb;
                Intent i = new Intent(Intent.ACTION_GET_CONTENT).addCategory(Intent.CATEGORY_OPENABLE).setType("*/*");
                try { startActivityForResult(Intent.createChooser(i, null), REQ_FILE); }
                catch (ActivityNotFoundException e) { fileCb = null; return false; }
                return true;  // Importar (Grupos, Carteira)
            }
        });
        if (Build.VERSION.SDK_INT >= 33)  // Android 13+: voltar (no 16 o onBackPressed não é mais chamado)
            getOnBackInvokedDispatcher().registerOnBackInvokedCallback(android.window.OnBackInvokedDispatcher.PRIORITY_DEFAULT, this::back);
        updater = new Updater(this);
        if (saved != null) web.restoreState(saved);
        else web.loadUrl(BuildConfig.SITE + "/" + acaoQuery(getIntent()));
    }

    /** Toque numa ação do widget: ?acao=TICKER (só letras e números). */
    private static String ticker(Intent i) {
        String t = i == null ? null : i.getStringExtra(FavWidget.EXTRA_TICKER);
        return t != null && t.matches("[A-Z0-9]{3,12}") ? t : null;
    }
    private static String acaoQuery(Intent i) { String t = ticker(i); return t == null ? "" : "?acao=" + t; }

    @Override protected void onNewIntent(Intent i) {
        super.onNewIntent(i);
        String t = ticker(i);
        if (t != null) web.evaluateJavascript("window.jgOpen ? jgOpen('" + t + "') : location.assign('/?acao=" + t + "')", null);
    }

    @Override protected void onSaveInstanceState(Bundle out) { super.onSaveInstanceState(out); web.saveState(out); }

    @Override protected void onActivityResult(int req, int res, Intent data) {
        if (req == REQ_FILE && fileCb != null) {
            Uri u = res == RESULT_OK && data != null ? data.getData() : null;
            fileCb.onReceiveValue(u != null ? new Uri[]{u} : null);
            fileCb = null;
            return;
        }
        super.onActivityResult(req, res, data);
    }

    private void back() { if (web.canGoBack()) web.goBack(); else moveTaskToBack(true); }

    @SuppressWarnings("deprecation")
    @Override public void onBackPressed() { back(); }

    @Override protected void onPause() { super.onPause(); web.onPause(); }
    @Override protected void onResume() { super.onResume(); web.onResume(); updater.onResume(); }

    /** window.JGApp no site (só existe dentro do app). */
    final class Bridge {
        /** Lista e ordem dos Favoritos (app.js → pushApp). Mudou: redesenha o widget e busca os preços. */
        @JavascriptInterface public void setFavs(String json) {
            if (json == null || json.length() > 20000) return;
            if (Store.setFavs(MainActivity.this, json)) {
                FavWidget.render(getApplicationContext());
                FavWidget.refreshAsync(getApplicationContext(), null);
            }
        }

        /** Exportar (ui.js → saveFile): grava o arquivo em Downloads. */
        @JavascriptInterface public void saveFile(String name, String type, String text) {
            String n = name == null ? "arquivo.txt" : name.replaceAll("[^A-Za-z0-9._-]", "_");
            String mime = type == null ? "text/plain" : type.split(";")[0];
            boolean ok;
            try {
                byte[] b = (text == null ? "" : text).getBytes(StandardCharsets.UTF_8);
                if (Build.VERSION.SDK_INT >= 29) {
                    ContentValues cv = new ContentValues();
                    cv.put(MediaStore.Downloads.DISPLAY_NAME, n);
                    cv.put(MediaStore.Downloads.MIME_TYPE, mime);
                    cv.put(MediaStore.Downloads.RELATIVE_PATH, Environment.DIRECTORY_DOWNLOADS);
                    Uri u = getContentResolver().insert(MediaStore.Downloads.EXTERNAL_CONTENT_URI, cv);
                    try (OutputStream o = getContentResolver().openOutputStream(u)) { o.write(b); }
                } else {
                    File d = getExternalFilesDir(Environment.DIRECTORY_DOWNLOADS);
                    try (OutputStream o = new FileOutputStream(new File(d, n))) { o.write(b); }
                }
                ok = true;
            } catch (Exception e) { ok = false; }
            final String msg = ok ? "Salvo em Downloads: " + n : "Não foi possível salvar o arquivo.";
            runOnUiThread(() -> Toast.makeText(MainActivity.this, msg, Toast.LENGTH_LONG).show());
        }
    }
}
