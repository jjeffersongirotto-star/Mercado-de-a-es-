package com.jginvesting.app;

import android.app.PendingIntent;
import android.appwidget.AppWidgetManager;
import android.appwidget.AppWidgetProvider;
import android.content.ComponentName;
import android.content.Context;
import android.content.Intent;
import android.net.Uri;
import android.os.Build;
import android.view.View;
import android.widget.RemoteViews;

import java.util.List;

/** Widget ★ Favoritos: preço, variação do dia e Barato/Caro de cada favorito. Atualiza a cada 30 min (widget_info) e no ⟳. */
public class FavWidget extends AppWidgetProvider {
    static final String ACTION_REFRESH = "com.jginvesting.app.REFRESH";
    static final String EXTRA_TICKER = "ticker";

    @Override public void onUpdate(Context c, AppWidgetManager m, int[] ids) {
        render(c);
        refreshAsync(c, goAsync());
    }

    @Override public void onReceive(Context c, Intent i) {
        if (ACTION_REFRESH.equals(i.getAction())) { render(c); refreshAsync(c, goAsync()); return; }
        super.onReceive(c, i);
    }

    /** Busca os dados dos favoritos e redesenha. pr = broadcast pendente (pode ser null quando chamado pelo app). */
    static void refreshAsync(Context ctx, PendingResult pr) {
        final Context c = ctx.getApplicationContext();
        new Thread(() -> {
            try {
                List<String> favs = WidgetData.favs(Store.favs(c));
                if (!favs.isEmpty()) {
                    String j = Api.widget(favs, pr != null ? 8000 : 30000);  // broadcast: o Android dá ~10 s
                    if (j != null) Store.setData(c, j);
                }
                render(c);
            } finally {
                if (pr != null) pr.finish();
            }
        }).start();
    }

    static int[] ids(Context c) {
        return AppWidgetManager.getInstance(c).getAppWidgetIds(new ComponentName(c, FavWidget.class));
    }

    /** Desenha todos os widgets com o que está guardado (Store). */
    static void render(Context c) {
        AppWidgetManager m = AppWidgetManager.getInstance(c);
        int[] ids = ids(c);
        if (ids.length == 0) return;
        List<String> favs = WidgetData.favs(Store.favs(c));
        String data = Store.data(c);
        List<WidgetData.Item> items = WidgetData.items(favs, data);
        int flagsImm = PendingIntent.FLAG_UPDATE_CURRENT | PendingIntent.FLAG_IMMUTABLE;
        int flagsMut = PendingIntent.FLAG_UPDATE_CURRENT | (Build.VERSION.SDK_INT >= 31 ? PendingIntent.FLAG_MUTABLE : 0);
        for (int id : ids) {
            RemoteViews v = new RemoteViews(c.getPackageName(), R.layout.widget);
            String up = WidgetData.updated(data);
            v.setTextViewText(R.id.w_time, up);
            v.setViewVisibility(R.id.w_time, up.isEmpty() ? View.GONE : View.VISIBLE);
            Intent open = new Intent(c, MainActivity.class).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK | Intent.FLAG_ACTIVITY_SINGLE_TOP);
            v.setOnClickPendingIntent(R.id.w_title, PendingIntent.getActivity(c, 0, open, flagsImm));
            Intent rf = new Intent(c, FavWidget.class).setAction(ACTION_REFRESH);
            v.setOnClickPendingIntent(R.id.w_refresh, PendingIntent.getBroadcast(c, 1, rf, flagsImm));
            // toque numa linha: abre o card da ação (o ticker vem no fill-in de cada linha)
            Intent tpl = new Intent(c, MainActivity.class).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK | Intent.FLAG_ACTIVITY_SINGLE_TOP);
            v.setPendingIntentTemplate(R.id.w_list, PendingIntent.getActivity(c, 2, tpl, flagsMut));
            v.setEmptyView(R.id.w_list, R.id.w_empty);
            if (Build.VERSION.SDK_INT >= 31) {
                RemoteViews.RemoteCollectionItems.Builder b = new RemoteViews.RemoteCollectionItems.Builder().setHasStableIds(true).setViewTypeCount(1);
                for (int i = 0; i < items.size(); i++) b.addItem(items.get(i).t.hashCode(), row(c, items.get(i)));
                v.setRemoteAdapter(R.id.w_list, b.build());
            } else {
                Intent svc = new Intent(c, WidgetService.class).putExtra(AppWidgetManager.EXTRA_APPWIDGET_ID, id);
                svc.setData(Uri.parse(svc.toUri(Intent.URI_INTENT_SCHEME)));
                legacyAdapter(v, svc);
            }
            m.updateAppWidget(id, v);
        }
        if (Build.VERSION.SDK_INT < 31) legacyNotify(m, ids);
    }

    @SuppressWarnings("deprecation")
    private static void legacyAdapter(RemoteViews v, Intent svc) { v.setRemoteAdapter(R.id.w_list, svc); }

    @SuppressWarnings("deprecation")
    private static void legacyNotify(AppWidgetManager m, int[] ids) { m.notifyAppWidgetViewDataChanged(ids, R.id.w_list); }

    /** Uma linha: ticker, preço, variação (verde/vermelho) e selo Barato/Caro. */
    static RemoteViews row(Context c, WidgetData.Item it) {
        RemoteViews r = new RemoteViews(c.getPackageName(), R.layout.widget_row);
        r.setTextViewText(R.id.r_ticker, it.t);
        r.setTextViewText(R.id.r_price, WidgetData.price(it.p));
        r.setTextViewText(R.id.r_var, WidgetData.change(it.v));
        r.setTextColor(R.id.r_var, c.getColor(it.v == null ? R.color.c_mut : it.v >= 0 ? R.color.c_pos : R.color.c_neg));
        r.setTextViewText(R.id.r_badge, WidgetData.badge(it.f));
        r.setTextColor(R.id.r_badge, c.getColor(it.f == null ? R.color.c_mut : it.f >= 0 ? R.color.c_pos : R.color.c_neg));
        r.setInt(R.id.r_badge, "setBackgroundResource", it.f == null ? R.drawable.chip_none : it.f >= 0 ? R.drawable.chip_pos : R.drawable.chip_neg);
        r.setOnClickFillInIntent(R.id.r_root, new Intent().putExtra(EXTRA_TICKER, it.t));
        return r;
    }
}
