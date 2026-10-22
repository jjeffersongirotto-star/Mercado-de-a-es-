package com.jginvesting.app;

import android.appwidget.AppWidgetManager;
import android.content.Context;
import android.os.Build;
import android.os.Bundle;
import android.os.Parcel;
import android.util.Log;
import android.widget.RemoteViews;

import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.concurrent.Executors;
import java.util.concurrent.ScheduledExecutorService;
import java.util.concurrent.TimeUnit;

/** 1.23: partes comuns aos dois widgets (Favoritos e Grupo simulação): desenho protegido, versões por tamanho com limite de
 *  tamanho da resposta e a fila do app (ponte do site). Regras sem Android em WidgetData (testadas na JVM). */
final class Widgets {
    private Widgets() { }
    static final String TAG = "JGWidget";

    /** Resposta ao Android (updateAppWidget) acima disso vai com menos versões: o binder recusa ~1 MB por transação, e cada
     *  versão de altura repete todas as linhas (os bitmaps vão uma vez só). */
    static final int MAX_PARCEL = 250_000;

    /** Prazo total de uma atualização dentro do broadcast (o Android dá ~10 s depois de goAsync) e fora dele (app, RefreshJob). */
    static final long BROADCAST_MS = 8_500, BACKGROUND_MS = 90_000;

    /** Erro ao desenhar ou ao entregar ao launcher (TransactionTooLarge, limite de memória de bitmaps, launcher reiniciando):
     *  fica no log e o widget segue com o desenho anterior — nunca derruba a busca, a oferta de atualização ou o app. */
    static void log(String what, Throwable e) { try { Log.w(TAG, what, e); } catch (RuntimeException ignored) { /* testes na JVM */ } }

    /** Desenha uma versão do widget no tamanho s. */
    interface Build1 { RemoteViews make(WidgetData.Size s); }

    /** Monta a resposta do widget id: Android 12+ com as versões de WidgetData.sizes (o launcher usa a que cabe no tamanho real);
     *  grande demais (MAX_PARCEL), refaz com 3 versões e, se ainda grande, uma só. Android 7–11: uma só. */
    static RemoteViews compose(Bundle op, boolean land, Build1 b) {
        int minW = op.getInt(AppWidgetManager.OPTION_APPWIDGET_MIN_WIDTH, 0), maxW = op.getInt(AppWidgetManager.OPTION_APPWIDGET_MAX_WIDTH, 0);
        int minH = op.getInt(AppWidgetManager.OPTION_APPWIDGET_MIN_HEIGHT, 0), maxH = op.getInt(AppWidgetManager.OPTION_APPWIDGET_MAX_HEIGHT, 0);
        int first = Build.VERSION.SDK_INT >= 31 ? WidgetData.FULL : WidgetData.ONE;
        RemoteViews v = null;
        for (int level = first; level <= WidgetData.ONE; level++) {
            List<WidgetData.Size> ss = WidgetData.sizes(minW, maxW, minH, maxH, land, level);
            if (ss.size() == 1) return b.make(ss.get(0));
            v = sized(ss, b);
            int n = parcelSize(v);
            if (n <= MAX_PARCEL) return v;
            log("resposta de " + n + " bytes com " + ss.size() + " versões", null);
        }
        return v;
    }

    /** Uma só versão, no tamanho atual (plano B quando o launcher recusa a resposta com várias). */
    static RemoteViews single(Bundle op, boolean land, Build1 b) {
        return b.make(WidgetData.sizes(op.getInt(AppWidgetManager.OPTION_APPWIDGET_MIN_WIDTH, 0), op.getInt(AppWidgetManager.OPTION_APPWIDGET_MAX_WIDTH, 0),
                op.getInt(AppWidgetManager.OPTION_APPWIDGET_MIN_HEIGHT, 0), op.getInt(AppWidgetManager.OPTION_APPWIDGET_MAX_HEIGHT, 0), land, WidgetData.ONE).get(0));
    }

    @android.annotation.TargetApi(31)
    private static RemoteViews sized(List<WidgetData.Size> ss, Build1 b) {
        Map<android.util.SizeF, RemoteViews> m = new LinkedHashMap<>();
        for (WidgetData.Size s : ss) m.put(new android.util.SizeF(s.w, s.h), b.make(s));
        return new RemoteViews(m);
    }

    /** Bytes da resposta como vai ao Android (bitmaps grandes podem ir à parte, em memória compartilhada). Erro = "grande demais". */
    static int parcelSize(RemoteViews v) {
        Parcel p = Parcel.obtain();
        try { v.writeToParcel(p, 0); return p.dataSize(); }
        catch (RuntimeException | OutOfMemoryError e) { return Integer.MAX_VALUE; }
        finally { p.recycle(); }
    }

    /** Entrega ao launcher; se recusar, tenta uma versão só (fallback); se ainda falhar, fica no log. */
    static void update(AppWidgetManager m, int id, RemoteViews v, java.util.function.Supplier<RemoteViews> fallback) {
        try { m.updateAppWidget(id, v); return; }
        catch (RuntimeException e) { log("updateAppWidget " + id, e); }
        try { RemoteViews f = fallback.get(); if (f != null && f != v) m.updateAppWidget(id, f); }
        catch (RuntimeException | OutOfMemoryError e) { log("updateAppWidget (uma versão) " + id, e); }
    }

    // ---------- fila do app (ponte do site: window.JGApp) ----------
    /** Uma thread só para o que a ponte do site e a abertura do app pedem aos widgets (antes: na thread do JavaBridge, desenhando
     *  na hora, e cada setFavs/setGroups lançava uma busca). */
    static final ScheduledExecutorService BG = Executors.newSingleThreadScheduledExecutor(r -> {
        Thread t = new Thread(r, "jg-widgets"); t.setDaemon(true); return t;
    });
    /** Pedidos de busca a menos disso um do outro viram uma busca só (WidgetData.Coalesce). */
    static final long COALESCE_MS = 2_000;

    /** Agenda task em COALESCE_MS, a não ser que já haja uma agendada que ainda não começou (ela já vai ler o estado novo). */
    static void coalesce(WidgetData.Coalesce q, Runnable task) {
        if (!q.claim()) return;
        BG.schedule(() -> { q.started(); try { task.run(); } catch (RuntimeException e) { log("fila", e); } }, COALESCE_MS, TimeUnit.MILLISECONDS);
    }

    /** Executa na fila (protegido). */
    static void post(Runnable task) {
        BG.execute(() -> { try { task.run(); } catch (RuntimeException | OutOfMemoryError e) { log("fila", e); } });
    }
}
