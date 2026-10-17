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

/** Widget JG Investing: Favoritos ou um grupo da aba Grupos (seletor no topo) com preço, variação, Barato/Caro e Medo e Ganância. Atualiza a cada 30 min (widget_info) e no ⟳. */
public class FavWidget extends AppWidgetProvider {
    static final String ACTION_REFRESH = "com.jginvesting.app.REFRESH";
    static final String EXTRA_TICKER = "ticker";
    static final String EXTRA_UPDATE = "update";

    @Override public void onUpdate(Context c, AppWidgetManager m, int[] ids) {
        render(c);
        refreshAsync(c, goAsync());
    }

    @Override public void onReceive(Context c, Intent i) {
        if (ACTION_REFRESH.equals(i.getAction())) {  // ⟳ e troca de grupo (PickerActivity): "Atualizando…" já e busca na hora
            Store.setLoading(c, System.currentTimeMillis()); render(c); refreshAsync(c, goAsync()); return;
        }
        super.onReceive(c, i);
    }

    /** Lista escolhida no widget (grupo que deixou de existir volta para Favoritos). */
    static String selOf(Context c, int id, List<WidgetData.Group> gs) {
        String s = Store.sel(c, id);
        return WidgetData.exists(s, gs) ? s : WidgetData.FAV;
    }

    /** Busca os dados de cada lista em uso e redesenha. pr = broadcast pendente (pode ser null quando chamado pelo app). */
    static void refreshAsync(Context ctx, PendingResult pr) {
        final Context c = ctx.getApplicationContext();
        final long start = System.currentTimeMillis();
        new Thread(() -> {
            try {
                List<WidgetData.Group> gs = WidgetData.groups(Store.groups(c));
                java.util.LinkedHashSet<String> sels = new java.util.LinkedHashSet<>();
                for (int id : ids(c)) sels.add(selOf(c, id, gs));
                for (String sel : sels) {
                    List<String> tk = WidgetData.tickers(sel, Store.favs(c), gs);
                    if (tk.isEmpty()) continue;
                    String j = Api.widget(tk, pr != null ? 8000 : 30000);  // broadcast: o Android dá ~10 s
                    if (j != null) Store.setData(c, sel, j);
                    // logos que faltam no aparelho (só na primeira vez de cada um; ficam guardados)
                    Logos.ensure(c, WidgetData.logos(WidgetData.items(tk, Store.data(c, sel))), pr != null ? start + 8500 : 0);
                }
                Store.setLoading(c, 0); render(c);  // dados novos na tela antes da conferência de versão
                Updater.quietCheck(c, pr != null ? 6000 : 20000);  // aviso "Atualização disponível" no topo
                render(c);
            } finally {
                if (Store.loading(c) != 0) { Store.setLoading(c, 0); render(c); }
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
        List<WidgetData.Group> gs = WidgetData.groups(Store.groups(c));
        int flagsImm = PendingIntent.FLAG_UPDATE_CURRENT | PendingIntent.FLAG_IMMUTABLE;
        int flagsMut = PendingIntent.FLAG_UPDATE_CURRENT | (Build.VERSION.SDK_INT >= 31 ? PendingIntent.FLAG_MUTABLE : 0);
        for (int id : ids) {
            String sel = selOf(c, id, gs), data = Store.data(c, sel);
            List<WidgetData.Item> items = WidgetData.items(WidgetData.tickers(sel, Store.favs(c), gs), data);
            java.util.Map<String, android.graphics.Bitmap> bmp = Logos.newCache();
            int px = Logos.px(c, items.size());
            WidgetData.Bands bands = WidgetData.bands(data);
            RemoteViews v = new RemoteViews(c.getPackageName(), R.layout.widget);
            String nm = WidgetData.name(sel, gs);
            v.setTextViewText(R.id.w_sel, nm + "  ▾");
            v.setTextViewText(R.id.w_sel2, nm + "  ▾");
            Intent pick = new Intent(c, PickerActivity.class).putExtra(AppWidgetManager.EXTRA_APPWIDGET_ID, id)
                    .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK | Intent.FLAG_ACTIVITY_MULTIPLE_TASK | Intent.FLAG_ACTIVITY_EXCLUDE_FROM_RECENTS);
            pick.setData(Uri.parse("jg://pick/" + id));  // um PendingIntent por widget
            v.setOnClickPendingIntent(R.id.w_sel, PendingIntent.getActivity(c, 100 + id, pick, flagsImm));
            v.setOnClickPendingIntent(R.id.w_sel2, PendingIntent.getActivity(c, 100 + id, pick, flagsImm));
            v.setTextViewText(R.id.w_empty, c.getString(WidgetData.FAV.equals(sel) ? R.string.widget_empty : R.string.widget_empty_group));
            boolean busy = System.currentTimeMillis() - Store.loading(c) < 25000;  // ⟳ / troca de grupo em andamento
            String up = busy ? c.getString(R.string.widget_loading) : WidgetData.updated(data);
            v.setTextViewText(R.id.w_time, up);
            v.setViewVisibility(R.id.w_time, up.isEmpty() ? View.GONE : View.VISIBLE);
            // marca comprida "JG Investing" ou, se o nome do grupo não couber ao lado dela, o logo quadrado (refeito ao redimensionar)
            android.os.Bundle op = m.getAppWidgetOptions(id);
            android.content.res.Configuration cf = c.getResources().getConfiguration();
            int hw = WidgetData.widthDp(op.getInt(AppWidgetManager.OPTION_APPWIDGET_MIN_WIDTH, 0), op.getInt(AppWidgetManager.OPTION_APPWIDGET_MAX_WIDTH, 0),
                    cf.orientation == android.content.res.Configuration.ORIENTATION_LANDSCAPE);
            float dens = c.getResources().getDisplayMetrics().density;
            boolean brand = WidgetData.longLogo(nm, hw, Math.round(c.getResources().getDimension(R.dimen.brand_w) / dens), cf.fontScale, !up.isEmpty());
            // nome curto: marca comprida até o seletor, que fica colado ao horário; nome longo: logo quadrado e seletor no meio
            v.setViewVisibility(R.id.w_brand, brand ? View.VISIBLE : View.GONE);
            v.setViewVisibility(R.id.w_sel2, brand ? View.VISIBLE : View.GONE);
            v.setViewVisibility(R.id.w_logo, brand ? View.GONE : View.VISIBLE);
            v.setViewVisibility(R.id.w_mid, brand ? View.GONE : View.VISIBLE);
            if (brand) {
                android.graphics.Bitmap bm = brandBitmap(c, Math.round((WidgetData.brandRoom(nm, hw, cf.fontScale, !up.isEmpty()) - 4) * dens), Math.round(30 * dens));
                if (bm != null) v.setImageViewBitmap(R.id.w_brand, bm);
            }
            Intent open = new Intent(c, MainActivity.class).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK | Intent.FLAG_ACTIVITY_SINGLE_TOP);
            v.setOnClickPendingIntent(R.id.w_logo, PendingIntent.getActivity(c, 0, open, flagsImm));
            v.setOnClickPendingIntent(R.id.w_brand, PendingIntent.getActivity(c, 0, open, flagsImm));
            UpdateLogic.Info nu = Updater.known(c);
            boolean upd = UpdateLogic.available(nu, BuildConfig.VERSION_CODE);
            v.setViewVisibility(R.id.w_upd, upd ? View.VISIBLE : View.GONE);
            if (upd) {
                v.setTextViewText(R.id.w_upd, c.getString(R.string.widget_update, nu.name));
                Intent ui = new Intent(c, MainActivity.class).putExtra(EXTRA_UPDATE, true).setAction("com.jginvesting.app.UPDATE")
                        .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK | Intent.FLAG_ACTIVITY_SINGLE_TOP);
                v.setOnClickPendingIntent(R.id.w_upd, PendingIntent.getActivity(c, 3, ui, flagsImm));
            }
            Intent rf = new Intent(c, FavWidget.class).setAction(ACTION_REFRESH);
            v.setOnClickPendingIntent(R.id.w_refresh, PendingIntent.getBroadcast(c, 1, rf, flagsImm));
            // toques nas linhas (abrir/fechar gráfico, marcar ponto, abrir no app): WidgetTap, sem tela; o que fazer vem no fill-in
            Intent tpl = new Intent(c, WidgetTap.class).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK | Intent.FLAG_ACTIVITY_NO_ANIMATION
                    | Intent.FLAG_ACTIVITY_EXCLUDE_FROM_RECENTS | Intent.FLAG_ACTIVITY_MULTIPLE_TASK);
            v.setPendingIntentTemplate(R.id.w_list, PendingIntent.getActivity(c, 2, tpl, flagsMut));
            v.setEmptyView(R.id.w_list, R.id.w_empty);
            if (Build.VERSION.SDK_INT >= 31) {
                RemoteViews.RemoteCollectionItems.Builder b = new RemoteViews.RemoteCollectionItems.Builder().setHasStableIds(true).setViewTypeCount(1);
                int wDp = AppWidgetManager.getInstance(c).getAppWidgetOptions(id).getInt(AppWidgetManager.OPTION_APPWIDGET_MIN_WIDTH, 300);
                for (int i = 0; i < items.size(); i++) b.addItem(items.get(i).t.hashCode(), row(c, items.get(i), bands, wDp, px, bmp));
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

    /** Marca comprida do tamanho do espaço: nome "JG Investing" na proporção original + gráfico da faixa esticado na horizontal
     *  (static/brand/jg-investing-widget-nome/-graf.png → ic_brand_nome/ic_brand_graf). null = usa a marca compacta (ic_brand). */
    static android.graphics.Bitmap brandBitmap(Context c, int roomPx, int hPx) {
        try {
            android.graphics.BitmapFactory.Options o = new android.graphics.BitmapFactory.Options(); o.inScaled = false;
            android.graphics.Bitmap n = android.graphics.BitmapFactory.decodeResource(c.getResources(), R.drawable.ic_brand_nome, o);
            android.graphics.Bitmap g = android.graphics.BitmapFactory.decodeResource(c.getResources(), R.drawable.ic_brand_graf, o);
            int nw = Math.round(n.getWidth() * (float) hPx / n.getHeight());
            int gmin = Math.round(190f * hPx / n.getHeight()), gnat = Math.round(g.getWidth() * (float) hPx / g.getHeight());
            int gw = WidgetData.brandGrafPx(roomPx, nw, gmin, gnat);
            android.graphics.Bitmap out = android.graphics.Bitmap.createBitmap(nw + gw, hPx, android.graphics.Bitmap.Config.ARGB_8888);
            android.graphics.Canvas cv = new android.graphics.Canvas(out);
            android.graphics.Paint p = new android.graphics.Paint(android.graphics.Paint.FILTER_BITMAP_FLAG | android.graphics.Paint.ANTI_ALIAS_FLAG);
            cv.drawBitmap(n, null, new android.graphics.Rect(0, 0, nw, hPx), p);
            cv.drawBitmap(g, null, new android.graphics.Rect(nw, 0, nw + gw, hPx), p);
            return out;
        } catch (Exception | OutOfMemoryError e) { return null; }
    }

    @SuppressWarnings("deprecation")
    private static void legacyAdapter(RemoteViews v, Intent svc) { v.setRemoteAdapter(R.id.w_list, svc); }

    @SuppressWarnings("deprecation")
    private static void legacyNotify(AppWidgetManager m, int[] ids) { m.notifyAppWidgetViewDataChanged(ids, R.id.w_list); }

    @Override public void onAppWidgetOptionsChanged(Context c, AppWidgetManager m, int id, android.os.Bundle o) { render(c); }

    /** Busca o gráfico de 5 anos da ação aberta (se o guardado tem mais de 6 h) e redesenha. */
    static void chartAsync(Context ctx, String t) {
        final Context c = ctx.getApplicationContext();
        if (Store.chart(c, t) != null && System.currentTimeMillis() - Store.chartAt(c, t) < 6 * 3600_000L) return;
        new Thread(() -> {
            String j = Api.chart(t, 30000);
            if (j != null && WidgetData.chart(j) != null) Store.setChart(c, t, j);
            else if (Store.chart(c, t) == null) Store.setChart(c, t, "{}");  // sem histórico: mostra "Sem dados"
            render(c);
        }).start();
    }

    static final int ZONES = 16;
    private static final int[] Z_IDS = {R.id.z0, R.id.z1, R.id.z2, R.id.z3, R.id.z4, R.id.z5, R.id.z6, R.id.z7,
            R.id.z8, R.id.z9, R.id.z10, R.id.z11, R.id.z12, R.id.z13, R.id.z14, R.id.z15};

    private static Intent tap(String a, String t, int z) {
        return new Intent().putExtra(WidgetTap.A, a).putExtra(WidgetTap.T, t).putExtra(WidgetTap.Z, z);
    }

    /** Uma linha: logo + Ação (nome curto embaixo) | Preço | Dia | Barato/Caro | Medo e Ganância; aberta, o gráfico de 5 anos com faixas de toque. */
    static RemoteViews row(Context c, WidgetData.Item it, WidgetData.Bands bands, int wDp) { return row(c, it, bands, wDp, Logos.px(c, 1), null); }

    /** Widget estreito (menos de NARROW dp): sem o logo, para o ticker caber. */
    static final int NARROW = 330;

    static RemoteViews row(Context c, WidgetData.Item it, WidgetData.Bands bands, int wDp, int px, java.util.Map<String, android.graphics.Bitmap> bmp) {
        RemoteViews r = new RemoteViews(c.getPackageName(), R.layout.widget_row);
        r.setTextViewText(R.id.r_ticker, it.t);
        boolean hasName = it.s != null && !it.s.isEmpty();
        r.setTextViewText(R.id.r_name, hasName ? it.s : "");
        r.setViewVisibility(R.id.r_name, hasName ? View.VISIBLE : View.GONE);
        boolean narrow = wDp < NARROW;
        r.setViewVisibility(R.id.r_slot, narrow ? View.GONE : View.VISIBLE);
        if (!narrow) {  // logo no formato original (fit-center no slot de 32dp); sem logo: círculo com as iniciais
            android.graphics.Bitmap lg = Logos.bitmap(c, it.l, px, bmp);
            if (lg != null) {
                r.setImageViewBitmap(R.id.r_logo, lg);
                r.setViewVisibility(R.id.r_logo, View.VISIBLE); r.setViewVisibility(R.id.r_ini, View.GONE);
            } else {
                r.setTextViewText(R.id.r_ini, WidgetData.initials(it.t));
                r.setViewVisibility(R.id.r_logo, View.GONE); r.setViewVisibility(R.id.r_ini, View.VISIBLE);
            }
        }
        r.setTextViewText(R.id.r_price, priceText(WidgetData.price(it.p, it.c)));
        r.setTextViewText(R.id.r_var, WidgetData.change(it.v));
        r.setTextColor(R.id.r_var, c.getColor(it.v == null ? R.color.c_mut : it.v >= 0 ? R.color.c_pos : R.color.c_neg));
        r.setTextViewText(R.id.r_badge, WidgetData.badge(it.f, it.x));
        r.setTextColor(R.id.r_badge, c.getColor(it.f == null ? R.color.c_mut : WidgetData.up(it.f) ? R.color.c_pos : R.color.c_neg));
        r.setInt(R.id.r_badge, "setBackgroundResource", it.f == null ? R.drawable.chip_none : WidgetData.up(it.f) ? R.drawable.chip_pos : R.drawable.chip_neg);
        if (it.g == null || bands.lim.length == 0) {
            r.setTextViewText(R.id.r_fg, "—"); r.setTextColor(R.id.r_fg, c.getColor(R.color.c_mut));
            r.setViewVisibility(R.id.r_fgn, View.GONE);
        } else {  // cor da faixa como no card (.fg-0 … .fg-4)
            int col = c.getColor(FG_COL[Math.min(FG_COL.length - 1, bands.index(it.g))]);
            r.setTextViewText(R.id.r_fg, String.valueOf(it.g)); r.setTextColor(R.id.r_fg, col);
            r.setTextViewText(R.id.r_fgn, bands.shortName(it.g)); r.setTextColor(R.id.r_fgn, col);
            r.setViewVisibility(R.id.r_fgn, View.VISIBLE);
        }
        r.setOnClickFillInIntent(R.id.r_main, tap("x", it.t, -1));
        boolean open = it.t.equals(Store.expanded(c));
        r.setViewVisibility(R.id.r_exp, open ? View.VISIBLE : View.GONE);
        if (!open) return r;
        r.setOnClickFillInIntent(R.id.r_open, tap("o", it.t, -1));
        String js = Store.chart(c, it.t);
        WidgetData.Chart ch = js == null ? null : WidgetData.chart(js);
        if (ch == null) {
            r.setTextViewText(R.id.r_tip, js == null ? "Carregando 5 anos…" : "Sem dados de preço");
            r.setViewVisibility(R.id.r_chartbox, View.GONE);
            return r;
        }
        int z = Store.zone(c), sel = z < 0 ? ch.size() - 1 : WidgetData.zonePoint(ch, z, ZONES);
        r.setTextViewText(R.id.r_tip, WidgetData.tip(ch, sel));
        float dd = Math.min(1.5f, c.getResources().getDisplayMetrics().density);  // ~160 KB por gráfico
        r.setViewVisibility(R.id.r_chartbox, View.VISIBLE);
        r.setImageViewBitmap(R.id.r_chart, ChartDraw.draw(c, ch, (int) ((wDp - 20) * dd), (int) (110 * dd), sel, dd));
        for (int i = 0; i < ZONES; i++) r.setOnClickFillInIntent(Z_IDS[i], tap("z", it.t, i));
        return r;
    }

    /** Preço com o símbolo da moeda menor (R$, US$, £, €, ¥), para caber na coluna sem desalinhar. */
    static CharSequence priceText(String s) {
        int i = s.indexOf(' ');
        if (i <= 0) return s;
        android.text.SpannableString sp = new android.text.SpannableString(s);
        sp.setSpan(new android.text.style.RelativeSizeSpan(0.72f), 0, i, android.text.Spanned.SPAN_EXCLUSIVE_EXCLUSIVE);
        return sp;
    }

    private static final int[] FG_COL = {R.color.c_neg, R.color.c_orange, R.color.c_amber, R.color.c_lime, R.color.c_pos};
}
