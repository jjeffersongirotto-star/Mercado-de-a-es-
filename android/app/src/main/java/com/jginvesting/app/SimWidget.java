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

/** Widget Grupo simulação: um Grupo simulação da aba Grupos (seletor no topo quando há mais de um) com Modelo | Carteira | Valor aportado |
 *  Valor atual | Variação do dia; tocar num modelo abre embaixo TODAS as posições (rolando) e o CDB, "↗ abrir" (movimentações do modelo no app);
 *  tocar numa empresa abre no app a janela só dela dentro do modelo.
 *  Dados: /api/widget/simgrupo (o mesmo cálculo da aba Grupos, com o preço de agora). Atualiza a cada 30 min e no ⟳. */
public class SimWidget extends AppWidgetProvider {
    static final String ACTION_REFRESH = "com.jginvesting.app.SIM_REFRESH", ACTION_XLSX = "com.jginvesting.app.SIM_XLSX";
    static final String EXTRA_SIM = "sim", EXTRA_MODEL = "model", EXTRA_TK = "tk";

    @Override public void onUpdate(Context c, AppWidgetManager m, int[] ids) { PendingResult pr = goAsync(); render(c); refreshAsync(c, pr, 0); }

    @Override public void onReceive(Context c, Intent i) {
        if (ACTION_XLSX.equals(i.getAction())) { download(c, i.getIntExtra(AppWidgetManager.EXTRA_APPWIDGET_ID, 0)); return; }
        if (ACTION_REFRESH.equals(i.getAction())) {  // ⟳ e troca de grupo: "Atualizando…" e busca na hora
            long tk = Store.startSimLoading(c); render(c);
            refreshAsync(c, goAsync(), tk); return;
        }
        super.onReceive(c, i);
    }

    @Override public void onAppWidgetOptionsChanged(Context c, AppWidgetManager m, int id, android.os.Bundle o) { render(c); }

    /** 1.23: widget removido: a escolha dele sai do aparelho; restaurado com id novo (backup): a escolha vai junto. */
    @Override public void onDeleted(Context c, int[] ids) { Store.forgetWidgets(c, "ssel_", ids); }
    @Override public void onRestored(Context c, int[] oldIds, int[] newIds) { Store.remapWidgets(c, "ssel_", oldIds, newIds); }

    /** ⬇: planilha do grupo do widget id (/api/widget/simgrupo.xlsx, gerada no servidor) pelo DownloadManager, em Downloads (Android 10+;
     *  antes, na pasta de downloads do sistema), com a notificação do sistema que abre o arquivo ao terminar. */
    static void download(Context c, int id) {
        SimData.Sim s = simOf(c, id, SimData.sims(Store.sims(c)));
        if (s == null) return;
        try {
            String file = SimData.fileName(s.name, new java.text.SimpleDateFormat("yyyy-MM-dd", java.util.Locale.US).format(new java.util.Date()));
            android.app.DownloadManager.Request r = new android.app.DownloadManager.Request(Uri.parse(BuildConfig.SITE + "/api/widget/simgrupo.xlsx?" + SimData.query(s)
                    + "&n=" + java.net.URLEncoder.encode(s.name, "UTF-8")))
                    .setTitle(file).setDescription(c.getString(R.string.sim_dl))
                    .setMimeType("application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
                    .setNotificationVisibility(android.app.DownloadManager.Request.VISIBILITY_VISIBLE_NOTIFY_COMPLETED);
            if (Build.VERSION.SDK_INT >= 29) r.setDestinationInExternalPublicDir(android.os.Environment.DIRECTORY_DOWNLOADS, file);
            ((android.app.DownloadManager) c.getSystemService(Context.DOWNLOAD_SERVICE)).enqueue(r);
            android.widget.Toast.makeText(c, "Baixando a planilha… (aparece nas notificações)", android.widget.Toast.LENGTH_SHORT).show();
        } catch (Exception e) {
            android.widget.Toast.makeText(c, "Não foi possível baixar a planilha.", android.widget.Toast.LENGTH_LONG).show();
        }
    }

    static int[] ids(Context c) { return AppWidgetManager.getInstance(c).getAppWidgetIds(new ComponentName(c, SimWidget.class)); }

    /** Grupo mostrado no widget id (o escolhido; se sumiu, o primeiro). */
    static SimData.Sim simOf(Context c, int id, List<SimData.Sim> ss) { return SimData.pick(Store.simSel(c, id), ss); }

    /** Busca cada grupo em uso e redesenha. 1.23: um prazo só para tudo (como FavWidget.refreshNow), resposta mais antiga que a
     *  guardada descartada (Store.nextReq + setSimDataIfNewer) e pr.finish() sempre. */
    static void refreshAsync(Context ctx, PendingResult pr, long token) {
        final Context c = ctx.getApplicationContext();
        new Thread(() -> {
            final long deadline = System.currentTimeMillis() + (pr != null ? Widgets.BROADCAST_MS : Widgets.BACKGROUND_MS);
            try {
                List<SimData.Sim> ss = SimData.sims(Store.sims(c));
                java.util.LinkedHashMap<String, SimData.Sim> use = new java.util.LinkedHashMap<>();
                for (int id : ids(c)) { SimData.Sim s = simOf(c, id, ss); if (s != null) use.put(SimData.key(s), s); }
                for (SimData.Sim s : use.values()) {
                    int t = WidgetData.budget(deadline, System.currentTimeMillis(), pr != null ? 8500 : 45000, 1500);  // 1º pedido do dia pode montar as tabelas no servidor
                    if (t == 0) break;
                    long req = Store.nextReq(c);
                    String j = Api.simgrupo(s, t);
                    if (j != null && !SimData.rows(j).isEmpty()) Store.setSimDataIfNewer(c, SimData.key(s), j, req);
                }
                java.util.HashSet<String> keep = new java.util.HashSet<>(); for (SimData.Sim s : ss) keep.add(SimData.key(s));
                Store.pruneSims(c, keep);
                if (token != 0) Store.endSimLoading(c, token);
                render(c);  // dados novos na tela antes da conferência de versão
                int t = WidgetData.budget(deadline, System.currentTimeMillis(), pr != null ? 5000 : 20000, 2500);
                if (t > 0 && Updater.quietCheck(c, t)) FavWidget.render(c);  // atualização de dados = confere a versão também
            } catch (RuntimeException | OutOfMemoryError e) {
                Widgets.log("SimWidget.refresh", e);
            } finally {
                try { if (token != 0) { Store.endSimLoading(c, token); render(c); } }
                catch (RuntimeException e) { Widgets.log("SimWidget.endLoading", e); }
                finally { if (pr != null) pr.finish(); }
            }
        }).start();
    }

    /** Desenha todos os widgets Grupo simulação. 1.23: protegido (ver FavWidget.render). */
    static void render(Context c) {
        try { draw(c); } catch (RuntimeException | OutOfMemoryError e) { Widgets.log("SimWidget.render", e); }
    }

    private static synchronized void draw(Context c) {
        AppWidgetManager m = AppWidgetManager.getInstance(c);
        int[] ids = ids(c);
        if (ids.length == 0) return;
        List<SimData.Sim> ss = SimData.sims(Store.sims(c));
        boolean busy = WidgetData.within(Store.simLoading(c), System.currentTimeMillis(), WidgetData.SIM_LOADING_MS);
        for (int id : ids) {
            try {
                Frame f = new Frame(c, m, id, ss, busy);
                Widgets.update(m, id, Widgets.compose(f.op, f.land, f::make), () -> Widgets.single(f.op, f.land, f::make));
            } catch (RuntimeException | OutOfMemoryError e) { Widgets.log("SimWidget " + id, e); }
        }
        if (Build.VERSION.SDK_INT < 31) legacyNotify(m, ids);
    }

    /** O que é igual em todas as versões de tamanho de um widget; make desenha uma versão (como FavWidget.Frame). */
    private static final class Frame {
        final Context c; final int id; final SimData.Sim s; final List<SimData.Sim> ss; final List<SimData.Row> rows;
        final String nm, selT, up, sub, om; final boolean land, anyOpen; final float dens;
        final android.os.Bundle op; final android.content.res.Configuration cf;
        final java.util.Map<String, android.graphics.Bitmap> bmp = Logos.newCache();
        final int flagsImm = PendingIntent.FLAG_UPDATE_CURRENT | PendingIntent.FLAG_IMMUTABLE;
        final int flagsMut = PendingIntent.FLAG_UPDATE_CURRENT | (Build.VERSION.SDK_INT >= 31 ? PendingIntent.FLAG_MUTABLE : 0);

        Frame(Context c, AppWidgetManager m, int id, List<SimData.Sim> ss, boolean busy) {
            this.c = c; this.id = id; this.ss = ss;
            s = simOf(c, id, ss);
            String key = SimData.key(s), data = s == null ? "{}" : Store.simData(c, key);
            rows = SimData.rows(data);
            op = m.getAppWidgetOptions(id);
            cf = c.getResources().getConfiguration();
            land = cf.orientation == android.content.res.Configuration.ORIENTATION_LANDSCAPE;
            dens = c.getResources().getDisplayMetrics().density;
            nm = s == null ? c.getString(R.string.sim_widget_name) : s.name;
            selT = nm + (ss.size() > 1 ? "  ▾" : "");
            long at = s == null ? 0 : Store.simAt(c, key);
            up = busy ? c.getString(R.string.widget_loading) : at > 0 ? WidgetData.fetched(at, java.util.TimeZone.getDefault()) : "";
            sub = s == null ? "" : "Desde " + SimData.since(s.di) + " · " + SimData.money(s.v0) + SimData.monthly(s) + " em cada modelo";
            om = openModel(c, s);
            boolean o = false; for (SimData.Row r : rows) if (r.m.equals(om)) o = true;
            anyOpen = o;
        }

        /** Uma versão do widget no tamanho s (sz.h = altura; sz.lw = largura da orientação dessa versão). */
        RemoteViews make(WidgetData.Size sz) {
            int hv = sz.h, hw = sz.lw;
            RemoteViews v = new RemoteViews(c.getPackageName(), R.layout.widget_sim);
            v.setTextViewText(R.id.s_sel, selT); v.setTextViewText(R.id.s_sel2, selT);
            if (ss.size() > 1) {  // seletor só com mais de um Grupo simulação (como o dos Favoritos)
                Intent pick = new Intent(c, PickerActivity.class).putExtra(AppWidgetManager.EXTRA_APPWIDGET_ID, id).putExtra(PickerActivity.EXTRA_SIM, true)
                        .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK | Intent.FLAG_ACTIVITY_MULTIPLE_TASK | Intent.FLAG_ACTIVITY_EXCLUDE_FROM_RECENTS);
                pick.setData(Uri.parse("jg://simpick/" + id));
                v.setOnClickPendingIntent(R.id.s_sel, PendingIntent.getActivity(c, 500 + id, pick, flagsImm));
                v.setOnClickPendingIntent(R.id.s_sel2, PendingIntent.getActivity(c, 500 + id, pick, flagsImm));
            } else { v.setOnClickPendingIntent(R.id.s_sel, openApp(c, s, null, 600 + id)); v.setOnClickPendingIntent(R.id.s_sel2, openApp(c, s, null, 600 + id)); }
            v.setOnClickPendingIntent(R.id.s_logo, openApp(c, null, null, 0)); v.setOnClickPendingIntent(R.id.s_brand, openApp(c, null, null, 0));
            v.setTextViewText(R.id.s_time, up);
            v.setViewVisibility(R.id.s_time, up.isEmpty() ? View.GONE : View.VISIBLE);
            // marca comprida "JG Investing" até o seletor (como no widget Favoritos) ou, com nome de grupo longo, o logo quadrado
            String bn = ss.size() > 1 ? nm : nm.substring(0, Math.max(0, nm.length() - 3));  // sem ▾ o chip é ~3 letras menor
            boolean brand = WidgetData.longLogo(bn, hw, Math.round(c.getResources().getDimension(R.dimen.brand_w) / dens), cf.fontScale, !up.isEmpty());
            v.setViewVisibility(R.id.s_brand, brand ? View.VISIBLE : View.GONE);
            v.setViewVisibility(R.id.s_sel2, brand ? View.VISIBLE : View.GONE);
            v.setViewVisibility(R.id.s_logo, brand ? View.GONE : View.VISIBLE);
            v.setViewVisibility(R.id.s_mid, brand ? View.GONE : View.VISIBLE);
            if (brand) {  // o mesmo bitmap em todas as versões do mesmo tamanho de marca
                android.graphics.Bitmap bm = FavWidget.brand(c, Math.round((WidgetData.brandRoom(bn, hw, cf.fontScale, !up.isEmpty()) - 4) * dens), Math.round(30 * dens), bmp);
                if (bm != null) v.setImageViewBitmap(R.id.s_brand, bm);
            }
            v.setTextViewText(R.id.s_sub, sub);
            v.setViewVisibility(R.id.s_sub, sub.isEmpty() ? View.GONE : View.VISIBLE);
            v.setTextViewText(R.id.s_empty, c.getString(s == null ? R.string.sim_empty : R.string.sim_wait));
            Intent rf = new Intent(c, SimWidget.class).setAction(ACTION_REFRESH);
            v.setOnClickPendingIntent(R.id.s_refresh, PendingIntent.getBroadcast(c, 11, rf, flagsImm));
            Intent dl = new Intent(c, SimWidget.class).setAction(ACTION_XLSX).putExtra(AppWidgetManager.EXTRA_APPWIDGET_ID, id);
            v.setOnClickPendingIntent(R.id.s_dl, PendingIntent.getBroadcast(c, 700 + id, dl, flagsImm));
            v.setViewVisibility(R.id.s_dl, s == null ? View.GONE : View.VISIBLE);
            Intent tpl = new Intent(c, WidgetTap.class).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK | Intent.FLAG_ACTIVITY_NO_ANIMATION
                    | Intent.FLAG_ACTIVITY_EXCLUDE_FROM_RECENTS | Intent.FLAG_ACTIVITY_MULTIPLE_TASK);
            v.setPendingIntentTemplate(R.id.s_list, PendingIntent.getActivity(c, 12, tpl, flagsMut));
            v.setEmptyView(R.id.s_list, R.id.s_empty);
            if (Build.VERSION.SDK_INT >= 31) {
                // linhas inteiras: títulos e "Desde…" com altura fixa; com tudo fechado as linhas que cabem esticam até a borda
                // 1.21: uma versão por altura possível (FavWidget: WidgetData.sizes)
                v.setViewLayoutHeight(R.id.s_cols, WidgetData.colsDp(cf.fontScale), android.util.TypedValue.COMPLEX_UNIT_DIP);
                if (!sub.isEmpty()) v.setViewLayoutHeight(R.id.s_sub, SimData.subDp(cf.fontScale), android.util.TypedValue.COMPLEX_UNIT_DIP);
                int rp = SimData.rowPx(hv, dens, cf.fontScale, !sub.isEmpty(), rows.size(), anyOpen);
                RemoteViews.RemoteCollectionItems.Builder b = new RemoteViews.RemoteCollectionItems.Builder().setHasStableIds(true).setViewTypeCount(VIEW_TYPES);
                for (SimData.Item it : SimData.items(rows, om)) {
                    RemoteViews iv = item(c, s, it);
                    if (rp > 0 && it.type == SimData.Item.ROW) iv.setViewLayoutHeight(R.id.q_main, rp, android.util.TypedValue.COMPLEX_UNIT_PX);
                    b.addItem(it.id(), iv);
                }
                v.setRemoteAdapter(R.id.s_list, b.build());
            } else {
                Intent svc = new Intent(c, SimWidgetService.class).putExtra(AppWidgetManager.EXTRA_APPWIDGET_ID, id);
                svc.setData(Uri.parse(svc.toUri(Intent.URI_INTENT_SCHEME)));
                legacyAdapter(v, svc);
            }
            return v;
        }
    }

    /** Abre o app (s e mid: nas movimentações desse modelo do grupo, o mesmo modal da aba Grupos). */
    static PendingIntent openApp(Context c, SimData.Sim s, String mid, int req) {
        Intent i = new Intent(c, MainActivity.class).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK | Intent.FLAG_ACTIVITY_SINGLE_TOP);
        if (s != null) i.putExtra(EXTRA_SIM, s.id);
        if (mid != null) i.putExtra(EXTRA_MODEL, mid);
        return PendingIntent.getActivity(c, req, i, PendingIntent.FLAG_UPDATE_CURRENT | PendingIntent.FLAG_IMMUTABLE);
    }

    static Intent tap(String a, String sim, String mid) {
        return new Intent().putExtra(WidgetTap.A, a).putExtra(EXTRA_SIM, sim).putExtra(EXTRA_MODEL, mid);
    }

    static final int VIEW_TYPES = 3;  // modelo, título das posições, empresa/CDB

    /** Modelo aberto neste grupo ("" = nenhum). */
    static String openModel(Context c, SimData.Sim s) {
        String e = Store.simExp(c), p = (s == null ? "" : s.id) + "|";
        return e != null && e.startsWith(p) ? e.substring(p.length()) : "";
    }

    /** Uma linha da lista: modelo (toque abre/fecha), título do modelo aberto com "↗ abrir", uma empresa (toque: janela dela no app) ou o CDB. */
    static RemoteViews item(Context c, SimData.Sim s, SimData.Item it) {
        String sid = s == null ? "" : s.id; SimData.Row r = it.row;
        if (it.type == SimData.Item.HEAD) {
            RemoteViews h = new RemoteViews(c.getPackageName(), R.layout.widget_sim_head);
            h.setTextViewText(R.id.h_ph, SimData.head(r));
            if (Build.VERSION.SDK_INT >= 31) h.setViewLayoutWidth(R.id.h_emp, SimData.empDp(r), android.util.TypedValue.COMPLEX_UNIT_DIP);
            h.setOnClickFillInIntent(R.id.h_open, tap("so", sid, r.m));
            return h;
        }
        if (it.type == SimData.Item.POS || it.type == SimData.Item.CDB) {
            RemoteViews pv = new RemoteViews(c.getPackageName(), R.layout.widget_sim_pos);
            if (Build.VERSION.SDK_INT >= 31) pv.setViewLayoutWidth(R.id.p_emp, SimData.empDp(r), android.util.TypedValue.COMPLEX_UNIT_DIP);  // Android 7–11: 96 dp
            if (it.type == SimData.Item.CDB) {
                pv.setTextViewText(R.id.p_name, "Caixa no CDB"); pv.setViewVisibility(R.id.p_t, View.GONE);
                pv.setViewVisibility(R.id.p_q, View.GONE); pv.setViewVisibility(R.id.p_pm, View.GONE);
                boolean cd = r.cdbAp > 0;  // servidor sem os dados do CDB (antigo): só o saldo, como antes
                pv.setViewVisibility(R.id.p_cj, cd ? View.VISIBLE : View.INVISIBLE);
                if (cd) {  // período todo: rendeu (juros) e % sobre tudo que já foi aplicado; Investido = tudo que já foi aplicado
                    pv.setTextViewText(R.id.p_cjv, "Rendeu " + SimData.money(r.cdbJ));
                    pv.setTextViewText(R.id.p_cjp, SimData.cdbPct(r)); pv.setTextColor(R.id.p_cjp, c.getColor(r.cdbJ >= 0 ? R.color.c_pos : R.color.c_neg));
                }
                pv.setTextViewText(R.id.p_inv, cd ? SimData.money(r.cdbAp) : "");
                pv.setTextViewText(R.id.p_v, SimData.money(r.cash)); pv.setTextColor(R.id.p_v, c.getColor(R.color.c_txt));
                String ap = r.cdbP > 0 ? SimData.total(r.cash, r.cdbP) : "";  // saldo de hoje × parte aplicada dele
                pv.setTextViewText(R.id.p_vp, ap); pv.setTextColor(R.id.p_vp, c.getColor(r.cash >= r.cdbP ? R.color.c_pos : R.color.c_neg));
                pv.setOnClickFillInIntent(R.id.p_row, tap("so", sid, r.m));
                return pv;
            }
            SimData.Pos p = it.pos; boolean nm = p.s != null && !p.s.isEmpty();
            pv.setTextViewText(R.id.p_name, nm ? p.s : p.t);
            pv.setTextViewText(R.id.p_t, nm ? p.t : "");
            pv.setViewVisibility(R.id.p_t, nm ? View.VISIBLE : View.GONE);
            pv.setViewVisibility(R.id.p_q, View.VISIBLE); pv.setViewVisibility(R.id.p_pm, View.VISIBLE); pv.setViewVisibility(R.id.p_cj, View.GONE);
            pv.setTextViewText(R.id.p_q, SimData.qty(p.q));
            pv.setTextViewText(R.id.p_pm, SimData.price(p.pm));
            pv.setTextViewText(R.id.p_inv, SimData.money(p.inv));
            int cor = c.getColor(p.v >= p.inv ? R.color.c_pos : R.color.c_neg);
            pv.setTextViewText(R.id.p_v, SimData.money(p.v)); pv.setTextColor(R.id.p_v, cor);
            pv.setTextViewText(R.id.p_vp, SimData.total(p.v, p.inv)); pv.setTextColor(R.id.p_vp, cor);  // rendimento da posição (atual ÷ investido)
            pv.setOnClickFillInIntent(R.id.p_row, tap("sp", sid, r.m).putExtra(EXTRA_TK, p.t));
            return pv;
        }
        RemoteViews q = new RemoteViews(c.getPackageName(), R.layout.widget_sim_row);
        q.setTextViewText(R.id.q_name, r.n);
        String tot = SimData.total(r.v, r.ap);
        q.setTextViewText(R.id.q_tot, tot.isEmpty() ? "" : tot + " desde o início");
        q.setTextColor(R.id.q_tot, c.getColor(r.v >= r.ap ? R.color.c_pos : R.color.c_neg));
        q.setTextViewText(R.id.q_np, String.valueOf(r.np));
        q.setTextViewText(R.id.q_ap, SimData.money(r.ap));
        q.setTextViewText(R.id.q_v, SimData.money(r.v));
        int dc = c.getColor(r.dp == null ? R.color.c_mut : r.dv >= 0 ? R.color.c_pos : R.color.c_neg);
        q.setTextViewText(R.id.q_dp, SimData.dayPct(r.dp)); q.setTextColor(R.id.q_dp, dc);
        q.setTextViewText(R.id.q_dv, r.dp == null ? "" : SimData.dayMoney(r.dv)); q.setTextColor(R.id.q_dv, dc);
        q.setOnClickFillInIntent(R.id.q_main, tap("sx", sid, r.m));
        return q;
    }

    @SuppressWarnings("deprecation")
    private static void legacyAdapter(RemoteViews v, Intent svc) { v.setRemoteAdapter(R.id.s_list, svc); }

    @SuppressWarnings("deprecation")
    private static void legacyNotify(AppWidgetManager m, int[] ids) { m.notifyAppWidgetViewDataChanged(ids, R.id.s_list); }
}
