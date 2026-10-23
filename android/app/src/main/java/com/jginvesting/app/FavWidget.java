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
    static final String ACTION_REFRESH = "com.jginvesting.app.REFRESH", ACTION_CHART = "com.jginvesting.app.CHART";
    static final String EXTRA_TICKER = "ticker";
    static final String EXTRA_UPDATE = "update";
    static final String EXTRA_FORCE = "force";

    @Override public void onUpdate(Context c, AppWidgetManager m, int[] ids) {
        PendingResult pr = goAsync();
        render(c);
        refreshAsync(c, pr);
    }

    @Override public void onReceive(Context c, Intent i) {
        if (ACTION_REFRESH.equals(i.getAction())) {  // ⟳ e troca de grupo (PickerActivity): "Atualizando…" já e busca na hora
            long tk = Store.startLoading(c); render(c);
            // ⟳: o servidor refaz os dados se estiverem velhos no pregão (RefreshJob espera e busca); troca de grupo: só busca
            if (i.getBooleanExtra(EXTRA_FORCE, false) && RefreshJob.schedule(c, tk)) return;
            refreshAsync(c, goAsync(), tk); return;
        }
        if (ACTION_CHART.equals(i.getAction())) {  // 1.23: gráfico pedido pelo WidgetTap (que já fechou): busca dentro deste broadcast
            String t = i.getStringExtra(EXTRA_TICKER);
            if (WidgetData.validTicker(t)) chartAsync(c, t, goAsync());
            return;
        }
        super.onReceive(c, i);
    }

    /** 1.23: widget removido: a escolha dele sai do aparelho; restaurado com id novo (backup): a escolha vai junto. */
    @Override public void onDeleted(Context c, int[] ids) { Store.forgetWidgets(c, "sel_", ids); }
    @Override public void onRestored(Context c, int[] oldIds, int[] newIds) { Store.remapWidgets(c, "sel_", oldIds, newIds); }

    /** Lista escolhida no widget (grupo que deixou de existir volta para Favoritos). */
    static String selOf(Context c, int id, List<WidgetData.Group> gs) {
        String s = Store.sel(c, id);
        return WidgetData.exists(s, gs) ? s : WidgetData.FAV;
    }

    /** Busca os dados de cada lista em uso e redesenha. pr = broadcast pendente (pode ser null quando chamado pelo app). */
    static void refreshAsync(Context ctx, PendingResult pr) { refreshAsync(ctx, pr, 0); }

    /** token = início do "Atualizando…" desta atualização (0 = atualização sem aviso); só ela o limpa (Store.endLoading). */
    static void refreshAsync(Context ctx, PendingResult pr, long token) {
        final Context c = ctx.getApplicationContext();
        new Thread(() -> refreshNow(c, pr, token)).start();
    }

    /** Busca e redesenha nesta thread (RefreshJob chama direto, depois de esperar o servidor).
     *  1.23: um prazo só para tudo (no broadcast, Widgets.BROADCAST_MS): cada pedido recebe o que falta (WidgetData.budget);
     *  dados na tela primeiro, depois os logos que faltam e, se ainda der tempo, a conferência de versão. pr.finish() sempre. */
    static void refreshNow(Context c, PendingResult pr, long token) {
        final long deadline = System.currentTimeMillis() + (pr != null ? Widgets.BROADCAST_MS : Widgets.BACKGROUND_MS);
        try {
            List<WidgetData.Group> gs = WidgetData.groups(Store.groups(c));
            java.util.LinkedHashSet<String> sels = new java.util.LinkedHashSet<>();
            for (int id : ids(c)) sels.add(selOf(c, id, gs));
            List<String> logos = new java.util.ArrayList<>();
            for (String sel : sels) {
                List<String> tk = WidgetData.tickers(sel, Store.favs(c), gs);
                if (tk.isEmpty()) continue;
                int t = WidgetData.budget(deadline, System.currentTimeMillis(), pr != null ? 8000 : 30000, 1500);
                if (t == 0) break;
                long req = Store.nextReq(c);  // resposta mais antiga que a guardada é descartada (troca rápida de grupo); contador que sobrevive ao reinício
                String j = Api.widget(tk, t);
                if (j != null) Store.setDataIfNewer(c, sel, j, req);
                for (String f : WidgetData.logos(WidgetData.items(tk, Store.data(c, sel)))) if (!logos.contains(f)) logos.add(f);
            }
            if (token != 0) Store.endLoading(c, token);
            render(c);  // dados novos na tela antes dos logos e da conferência de versão
            // logos que faltam no aparelho (só na primeira vez de cada um; ficam guardados), dentro do mesmo prazo
            if (Logos.ensure(c, logos, deadline)) render(c);
            // 1.25: linha aberta sem gráfico guardado (busca do toque falhou): busca de novo aqui, com o tempo que sobrar
            // (no RefreshJob em segundo plano, até 60 s)
            String ex = Store.expanded(c);
            if (WidgetData.validTicker(ex) && Store.chart(c, ex) == null && LOADING.add(ex)) {
                try {
                    int ct = WidgetData.budget(deadline, System.currentTimeMillis(), pr != null ? 8000 : 60000, 1500);
                    if (ct > 0) { render(c); fetchChart(c, ex, ct); }
                } finally { LOADING.remove(ex); render(c); }
            }
            int t = WidgetData.budget(deadline, System.currentTimeMillis(), pr != null ? 6000 : 20000, 2500);
            if (t > 0 && Updater.quietCheck(c, t)) render(c);  // aviso "Atualização disponível" no topo
        } catch (RuntimeException | OutOfMemoryError e) {
            Widgets.log("FavWidget.refreshNow", e);
        } finally {
            try { if (token != 0 && Store.endLoading(c, token)) render(c); }
            catch (RuntimeException e) { Widgets.log("FavWidget.endLoading", e); }
            finally { if (pr != null) pr.finish(); }
        }
    }

    static int[] ids(Context c) {
        return AppWidgetManager.getInstance(c).getAppWidgetIds(new ComponentName(c, FavWidget.class));
    }

    /** Desenha todos os widgets com o que está guardado (Store). 1.23: protegido — erro do launcher (resposta grande demais,
     *  memória de bitmaps) fica no log e não derruba quem chamou (busca, WidgetTap, app, ponte do site). */
    static void render(Context c) {
        try { draw(c); } catch (RuntimeException | OutOfMemoryError e) { Widgets.log("FavWidget.render", e); }
    }

    private static synchronized void draw(Context c) {  // um desenho por vez: o mais recente lê o grupo escolhido por último e é o último enviado
        AppWidgetManager m = AppWidgetManager.getInstance(c);
        int[] ids = ids(c);
        if (ids.length == 0) return;
        List<WidgetData.Group> gs = WidgetData.groups(Store.groups(c));
        boolean busy = WidgetData.within(Store.loading(c), System.currentTimeMillis(), WidgetData.LOADING_MS);  // ⟳ / troca de grupo em andamento
        for (int id : ids) {
            try {
                Frame f = new Frame(c, m, id, gs, busy);
                Widgets.update(m, id, Widgets.compose(f.op, f.land, f::make), () -> Widgets.single(f.op, f.land, f::make));
            } catch (RuntimeException | OutOfMemoryError e) { Widgets.log("FavWidget " + id, e); }
        }
        if (Build.VERSION.SDK_INT < 31) legacyNotify(m, ids);
    }

    /** O que é igual em todas as versões de tamanho de um widget; make desenha uma versão. Bitmaps (logos, marca, gráfico) num
     *  mapa só (bmp): o mesmo objeto em todas as versões, que o Android manda uma vez. */
    private static final class Frame {
        final Context c; final int id; final String sel, nm, data, up; final List<WidgetData.Item> items;
        final java.util.Map<String, android.graphics.Bitmap> bmp = Logos.newCache();
        final int px, wDp; final WidgetData.Bands bands; final android.os.Bundle op; final android.content.res.Configuration cf;
        final boolean land, upd; final float dens; final WidgetData.Cols cols; final UpdateLogic.Info nu;
        final int flagsImm = PendingIntent.FLAG_UPDATE_CURRENT | PendingIntent.FLAG_IMMUTABLE;
        final int flagsMut = PendingIntent.FLAG_UPDATE_CURRENT | (Build.VERSION.SDK_INT >= 31 ? PendingIntent.FLAG_MUTABLE : 0);

        Frame(Context c, AppWidgetManager m, int id, List<WidgetData.Group> gs, boolean busy) {
            this.c = c; this.id = id;
            sel = selOf(c, id, gs); data = Store.data(c, sel); nm = WidgetData.name(sel, gs);
            items = WidgetData.items(WidgetData.tickers(sel, Store.favs(c), gs), data);
            px = Logos.px(c, items.size());
            bands = WidgetData.bands(data);
            op = m.getAppWidgetOptions(id);
            cf = c.getResources().getConfiguration();
            land = cf.orientation == android.content.res.Configuration.ORIENTATION_LANDSCAPE;
            dens = c.getResources().getDisplayMetrics().density;
            wDp = op.getInt(AppWidgetManager.OPTION_APPWIDGET_MIN_WIDTH, 300);
            cols = colsOf(c, items, wDp, cf.fontScale, dens);
            // horário = quando a última atualização terminou (dados chegaram); sem isso ainda, o horário dos dados no site
            long fat = Store.fetchedAt(c, sel);
            up = busy ? c.getString(R.string.widget_loading) : fat > 0 ? WidgetData.fetched(fat, java.util.TimeZone.getDefault()) : WidgetData.updated(data);
            nu = Updater.known(c);
            upd = UpdateLogic.available(nu, BuildConfig.VERSION_CODE, BuildConfig.VERSION_NAME);
        }

        /** Uma versão do widget no tamanho s (s.h = altura; s.lw = largura da orientação dessa versão). */
        RemoteViews make(WidgetData.Size s) {
            int hv = s.h, hw = s.lw;
            RemoteViews v = new RemoteViews(c.getPackageName(), R.layout.widget);
            v.setTextViewText(R.id.w_sel, nm + "  ▾");
            v.setTextViewText(R.id.w_sel2, nm + "  ▾");
            Intent pick = new Intent(c, PickerActivity.class).putExtra(AppWidgetManager.EXTRA_APPWIDGET_ID, id)
                    .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK | Intent.FLAG_ACTIVITY_MULTIPLE_TASK | Intent.FLAG_ACTIVITY_EXCLUDE_FROM_RECENTS);
            pick.setData(Uri.parse("jg://pick/" + id));  // um PendingIntent por widget
            v.setOnClickPendingIntent(R.id.w_sel, PendingIntent.getActivity(c, 100 + id, pick, flagsImm));
            v.setOnClickPendingIntent(R.id.w_sel2, PendingIntent.getActivity(c, 100 + id, pick, flagsImm));
            v.setTextViewText(R.id.w_empty, c.getString(WidgetData.FAV.equals(sel) ? R.string.widget_empty : R.string.widget_empty_group));
            v.setTextViewText(R.id.w_time, up);
            v.setViewVisibility(R.id.w_time, up.isEmpty() ? View.GONE : View.VISIBLE);
            // marca comprida "JG Investing" ou, se o nome do grupo não couber ao lado dela, o logo quadrado (refeito ao redimensionar)
            boolean brand = WidgetData.longLogo(nm, hw, Math.round(c.getResources().getDimension(R.dimen.brand_w) / dens), cf.fontScale, !up.isEmpty());
            // nome curto: marca comprida até o seletor, que fica colado ao horário; nome longo: logo quadrado e seletor no meio
            v.setViewVisibility(R.id.w_brand, brand ? View.VISIBLE : View.GONE);
            v.setViewVisibility(R.id.w_sel2, brand ? View.VISIBLE : View.GONE);
            v.setViewVisibility(R.id.w_logo, brand ? View.GONE : View.VISIBLE);
            v.setViewVisibility(R.id.w_mid, brand ? View.GONE : View.VISIBLE);
            if (brand) {  // o mesmo bitmap em todas as versões do mesmo tamanho de marca (o Android guarda uma vez só)
                android.graphics.Bitmap bm = brand(c, Math.round((WidgetData.brandRoom(nm, hw, cf.fontScale, !up.isEmpty()) - 4) * dens), Math.round(30 * dens), bmp);
                if (bm != null) v.setImageViewBitmap(R.id.w_brand, bm);
            }
            Intent open = new Intent(c, MainActivity.class).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK | Intent.FLAG_ACTIVITY_SINGLE_TOP);
            v.setOnClickPendingIntent(R.id.w_logo, PendingIntent.getActivity(c, 0, open, flagsImm));
            v.setOnClickPendingIntent(R.id.w_brand, PendingIntent.getActivity(c, 0, open, flagsImm));
            v.setViewVisibility(R.id.w_upd, upd ? View.VISIBLE : View.GONE);
            if (upd) {
                v.setTextViewText(R.id.w_upd, c.getString(R.string.widget_update, nu.name));
                Intent ui = new Intent(c, MainActivity.class).putExtra(EXTRA_UPDATE, true).setAction("com.jginvesting.app.UPDATE")
                        .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK | Intent.FLAG_ACTIVITY_SINGLE_TOP);
                v.setOnClickPendingIntent(R.id.w_upd, PendingIntent.getActivity(c, 3, ui, flagsImm));
            }
            Intent rf = new Intent(c, FavWidget.class).setAction(ACTION_REFRESH).putExtra(EXTRA_FORCE, true);
            v.setOnClickPendingIntent(R.id.w_refresh, PendingIntent.getBroadcast(c, 1, rf, flagsImm));
            // toques nas linhas (abrir/fechar gráfico, marcar ponto, abrir no app): WidgetTap, sem tela; o que fazer vem no fill-in
            Intent tpl = new Intent(c, WidgetTap.class).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK | Intent.FLAG_ACTIVITY_NO_ANIMATION
                    | Intent.FLAG_ACTIVITY_EXCLUDE_FROM_RECENTS | Intent.FLAG_ACTIVITY_MULTIPLE_TASK);
            v.setPendingIntentTemplate(R.id.w_list, PendingIntent.getActivity(c, 2, tpl, flagsMut));
            v.setEmptyView(R.id.w_list, R.id.w_empty);
            if (Build.VERSION.SDK_INT >= 31) {
                // 1.12: N linhas inteiras na altura do widget, a última rente à borda (títulos com altura fixa para a conta fechar);
                // 1.21: uma versão por altura possível (hv): o Android usa a maior que cabe no tamanho real
                v.setViewLayoutHeight(R.id.w_cols, WidgetData.colsDp(cf.fontScale), android.util.TypedValue.COMPLEX_UNIT_DIP);
                // 1.21: coluna Ação do tamanho do maior nome; a sobra vai igual para Preço, Dia, Barato/Caro e Medo e Ganância
                for (int k = 0; k < COL_IDS.length; k++)
                    v.setViewLayoutWidth(COL_IDS[k], colDp(c, k) + cols.extra / 4f, android.util.TypedValue.COMPLEX_UNIT_DIP);
                int listPx = Math.round((hv - WidgetData.headerDp(cf.fontScale, upd)) * dens);
                int rowPx = hv > 0 ? WidgetData.rows(listPx, dens, cf.fontScale, items.size())[1] : 0;
                RemoteViews.RemoteCollectionItems.Builder b = new RemoteViews.RemoteCollectionItems.Builder().setHasStableIds(true).setViewTypeCount(1);
                for (int i = 0; i < items.size(); i++) b.addItem(items.get(i).t.hashCode(), row(c, items.get(i), bands, wDp, px, bmp, rowPx, cols, i));
                v.setRemoteAdapter(R.id.w_list, b.build());
            } else {
                Intent svc = new Intent(c, WidgetService.class).putExtra(AppWidgetManager.EXTRA_APPWIDGET_ID, id);
                svc.setData(Uri.parse(svc.toUri(Intent.URI_INTENT_SCHEME)));
                legacyAdapter(v, svc);
            }
            return v;
        }
    }

    /** 1.23: marcas já desenhadas, por tamanho (entre um desenho e outro); render = o mesmo objeto em todas as versões do desenho. */
    private static final android.util.LruCache<String, android.graphics.Bitmap> BRAND = new android.util.LruCache<>(6);

    static android.graphics.Bitmap brand(Context c, int roomPx, int hPx, java.util.Map<String, android.graphics.Bitmap> render) {
        String k = "brand:" + roomPx + "x" + hPx;
        if (render != null && render.containsKey(k)) return render.get(k);
        android.graphics.Bitmap b = BRAND.get(k);
        if (b == null && (b = brandBitmap(c, roomPx, hPx)) != null) BRAND.put(k, b);
        if (render != null) render.put(k, b);
        return b;
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

    /** Busca o gráfico de 5 anos da ação aberta (se o guardado tem mais de 6 h, ou é do "futuro": relógio voltou) e redesenha.
     *  1.23: roda no broadcast ACTION_CHART (pr, goAsync), não numa thread solta do WidgetTap, que fecha na hora (no Android 14+
     *  o processo em segundo plano podia ficar congelado e o gráfico nunca chegava). pr.finish() sempre. */
    static void chartAsync(Context ctx, String t, PendingResult pr) {
        final Context c = ctx.getApplicationContext();
        if (Store.chart(c, t) != null && WidgetData.within(Store.chartAt(c, t), System.currentTimeMillis(), WidgetData.CHART_FRESH_MS)) {
            if (pr != null) pr.finish();
            return;
        }
        if (!LOADING.add(t)) { if (pr != null) pr.finish(); return; }  // já buscando
        render(c);  // 1.25: "Carregando 5 anos…" no lugar do "Sem conexão" ao tentar de novo
        new Thread(() -> {
            try {
                fetchChart(c, t, pr != null ? (int) Widgets.BROADCAST_MS : 30000);
            } catch (RuntimeException e) {
                Widgets.log("FavWidget.chartAsync", e);
            } finally { LOADING.remove(t); render(c); if (pr != null) pr.finish(); }
        }).start();
    }

    /** 1.25: ações com busca do gráfico em andamento; sem gráfico guardado e fora daqui = "Sem conexão, toque para tentar de novo"
     *  (falhou, esgotou o tempo ou o processo morreu no meio). Nunca mais fica preso em "Carregando 5 anos…". */
    static final java.util.Set<String> LOADING = java.util.concurrent.ConcurrentHashMap.newKeySet();

    /** Busca e guarda; sem resposta (rede/tempo) não guarda nada, para a próxima atualização tentar de novo. */
    static boolean fetchChart(Context c, String t, int timeoutMs) {
        String j = Api.chart(t, timeoutMs);
        if (j == null) return false;
        if (WidgetData.chart(j) != null) Store.setChart(c, t, j);
        else if (Store.chart(c, t) == null) Store.setChart(c, t, "{}");  // sem histórico: mostra "Sem dados"
        return true;
    }

    static final int ZONES = 16;
    private static final int[] Z_IDS = {R.id.z0, R.id.z1, R.id.z2, R.id.z3, R.id.z4, R.id.z5, R.id.z6, R.id.z7,
            R.id.z8, R.id.z9, R.id.z10, R.id.z11, R.id.z12, R.id.z13, R.id.z14, R.id.z15};

    private static Intent tap(String a, String t, int z) {
        return new Intent().putExtra(WidgetTap.A, a).putExtra(WidgetTap.T, t).putExtra(WidgetTap.Z, z);
    }

    /** Widget estreito (menos de NARROW dp): sem o logo, para o ticker caber. */
    static final int NARROW = 330;

    /** Uma linha: logo + Ação (nome curto embaixo) | Preço | Dia | Barato/Caro | Medo e Ganância; aberta, o gráfico de 5 anos com faixas de toque. */
    static RemoteViews row(Context c, WidgetData.Item it, WidgetData.Bands bands, int wDp, int px, java.util.Map<String, android.graphics.Bitmap> bmp) {
        return row(c, it, bands, wDp, px, bmp, 0, null, 0);
    }

    /** Colunas Preço, Dia, Barato/Caro e Medo e Ganância (títulos e linhas) e a largura padrão de cada uma (dimens.xml). */
    private static final int[] COL_IDS = {R.id.h_p, R.id.h_v, R.id.h_f, R.id.h_g}, ROW_COL_IDS = {R.id.r_price, R.id.r_vcol, R.id.r_fcol, R.id.r_gcol};
    private static final int[] COL_DIM = {R.dimen.col_p, R.dimen.col_v, R.dimen.col_f, R.dimen.col_g};

    static float colDp(Context c, int k) { return c.getResources().getDimension(COL_DIM[k]) / c.getResources().getDisplayMetrics().density; }

    /** 1.21: largura da coluna Ação pelo maior nome, medida com a fonte de verdade (negrito, escala de fonte do aparelho). */
    static WidgetData.Cols colsOf(Context c, List<WidgetData.Item> items, int wDp, float fontScale, float dens) {
        List<String> top = new java.util.ArrayList<>(), sub = new java.util.ArrayList<>();
        for (WidgetData.Item it : items) {
            boolean hasName = it.s != null && !it.s.isEmpty();
            top.add(hasName ? it.s : it.t); sub.add(hasName ? it.t : "");
        }
        android.graphics.Paint pb = new android.graphics.Paint(android.graphics.Paint.ANTI_ALIAS_FLAG), pr = new android.graphics.Paint(android.graphics.Paint.ANTI_ALIAS_FLAG);
        pb.setTypeface(android.graphics.Typeface.DEFAULT_BOLD); pr.setTypeface(android.graphics.Typeface.DEFAULT);
        WidgetData.Meas m = (s, sp, bold) -> { android.graphics.Paint p = bold ? pb : pr; p.setTextSize(sp * fontScale * dens); return p.measureText(s) / dens; };
        // −6 dp: o launcher pode informar o widget um pouco mais largo do que é; a sobra fica na coluna Ação
        return WidgetData.cols(top, sub, WidgetData.nameRoomDp(wDp, wDp < NARROW) - 6, m);
    }

    /** rowPx > 0 (Android 12+): altura da linha (WidgetData.rows), para a lista fechar em linhas inteiras; cols (1.21): tamanho do
     *  nome desta linha (i) e largura das outras colunas. */
    static RemoteViews row(Context c, WidgetData.Item it, WidgetData.Bands bands, int wDp, int px, java.util.Map<String, android.graphics.Bitmap> bmp, int rowPx,
                           WidgetData.Cols cols, int idx) {
        RemoteViews r = new RemoteViews(c.getPackageName(), R.layout.widget_row);
        if (rowPx > 0 && Build.VERSION.SDK_INT >= 31) r.setViewLayoutHeight(R.id.r_main, rowPx, android.util.TypedValue.COMPLEX_UNIT_PX);
        // nome popular em cima (negrito, maior que cabe) e o ticker embaixo (cinza); sem nome: só o ticker em cima
        boolean hasName = it.s != null && !it.s.isEmpty();
        boolean narrow = wDp < NARROW;
        String top = hasName ? it.s : it.t;
        r.setTextViewText(R.id.r_ticker, top);
        r.setTextViewTextSize(R.id.r_ticker, android.util.TypedValue.COMPLEX_UNIT_SP, cols != null ? cols.sp[idx] : WidgetData.nameSp(top, WidgetData.nameRoomDp(wDp, narrow)));
        if (cols != null && Build.VERSION.SDK_INT >= 31)
            for (int k = 0; k < ROW_COL_IDS.length; k++) r.setViewLayoutWidth(ROW_COL_IDS[k], colDp(c, k) + cols.extra / 4f, android.util.TypedValue.COMPLEX_UNIT_DIP);
        r.setTextViewText(R.id.r_name, hasName ? it.t : "");
        r.setViewVisibility(R.id.r_name, hasName ? View.VISIBLE : View.GONE);
        r.setViewVisibility(R.id.r_slot, narrow ? View.GONE : View.VISIBLE);
        if (!narrow) {  // logo no formato original (fit-center no slot de 32dp); sem logo: círculo com as iniciais
            // logo da própria ação (arquivo da mesma resposta); ainda não baixado: iniciais e imagem limpa (linha reaproveitada
            // pelo launcher não fica com o logo de outra empresa)
            String lf = WidgetData.logoFile(it, f -> new java.io.File(Logos.dir(c), f).exists());
            android.graphics.Bitmap lg = Logos.bitmap(c, lf, px, bmp);
            r.setContentDescription(R.id.r_logo, it.t);
            if (lg != null) {
                r.setImageViewBitmap(R.id.r_logo, lg);
                r.setViewVisibility(R.id.r_logo, View.VISIBLE); r.setViewVisibility(R.id.r_ini, View.GONE);
            } else {
                r.setTextViewText(R.id.r_ini, WidgetData.initials(it.t));
                r.setImageViewResource(R.id.r_logo, android.R.color.transparent);
                r.setViewVisibility(R.id.r_logo, View.GONE); r.setViewVisibility(R.id.r_ini, View.VISIBLE);
            }
        }
        r.setTextViewText(R.id.r_price, priceText(WidgetData.price(it.p, it.c)));
        r.setTextViewText(R.id.r_var, WidgetData.change(it.v));
        r.setTextColor(R.id.r_var, c.getColor(it.v == null ? R.color.c_mut : it.v >= 0 ? R.color.c_pos : R.color.c_neg));
        String va = WidgetData.changeAbs(it.p, it.v, it.c);
        r.setTextViewText(R.id.r_vabs, va);
        r.setViewVisibility(R.id.r_vabs, va.isEmpty() ? View.GONE : View.VISIBLE);
        r.setTextColor(R.id.r_vabs, c.getColor(it.v == null ? R.color.c_mut : it.v >= 0 ? R.color.c_pos : R.color.c_neg));
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
        r.setOnClickFillInIntent(R.id.r_tip, tap("c", it.t, -1));  // 1.25: toque tenta de novo (com gráfico guardado e recente, nada a fazer)
        String js = Store.chart(c, it.t);
        WidgetData.Chart ch = js == null ? null : WidgetData.chart(js);
        if (ch == null) {
            boolean busy = LOADING.contains(it.t);
            r.setTextViewText(R.id.r_tip, js != null ? "Sem dados de preço" : busy ? "Carregando 5 anos…" : "Sem conexão, toque para tentar de novo");
            r.setViewVisibility(R.id.r_chartbox, View.GONE);
            return r;
        }
        int z = Store.zone(c), sel = z < 0 ? ch.size() - 1 : WidgetData.zonePoint(ch, z, ZONES);
        r.setTextViewText(R.id.r_tip, WidgetData.tip(ch, sel));
        float dd = Math.min(1.5f, c.getResources().getDisplayMetrics().density);  // ~160 KB por gráfico
        r.setViewVisibility(R.id.r_chartbox, View.VISIBLE);
        String ck = "chart:" + it.t;  // o mesmo bitmap em todas as versões de altura (1.21)
        android.graphics.Bitmap cb = bmp != null ? bmp.get(ck) : null;
        if (cb == null) { cb = ChartDraw.draw(c, ch, (int) ((wDp - 20) * dd), (int) (110 * dd), sel, dd); if (bmp != null) bmp.put(ck, cb); }
        r.setImageViewBitmap(R.id.r_chart, cb);
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
