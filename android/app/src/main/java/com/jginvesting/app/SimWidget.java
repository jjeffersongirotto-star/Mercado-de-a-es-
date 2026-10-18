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
    static final String ACTION_REFRESH = "com.jginvesting.app.SIM_REFRESH";
    static final String EXTRA_SIM = "sim", EXTRA_MODEL = "model", EXTRA_TK = "tk";

    @Override public void onUpdate(Context c, AppWidgetManager m, int[] ids) { render(c); refreshAsync(c, goAsync(), 0); }

    @Override public void onReceive(Context c, Intent i) {
        if (ACTION_REFRESH.equals(i.getAction())) {  // ⟳ e troca de grupo: "Atualizando…" e busca na hora
            long tk = System.currentTimeMillis(); Store.setSimLoading(c, tk); render(c);
            refreshAsync(c, goAsync(), tk); return;
        }
        super.onReceive(c, i);
    }

    @Override public void onAppWidgetOptionsChanged(Context c, AppWidgetManager m, int id, android.os.Bundle o) { render(c); }

    static int[] ids(Context c) { return AppWidgetManager.getInstance(c).getAppWidgetIds(new ComponentName(c, SimWidget.class)); }

    /** Grupo mostrado no widget id (o escolhido; se sumiu, o primeiro). */
    static SimData.Sim simOf(Context c, int id, List<SimData.Sim> ss) { return SimData.pick(Store.simSel(c, id), ss); }

    static void refreshAsync(Context ctx, PendingResult pr, long token) {
        final Context c = ctx.getApplicationContext();
        new Thread(() -> {
            try {
                List<SimData.Sim> ss = SimData.sims(Store.sims(c));
                java.util.LinkedHashMap<String, SimData.Sim> use = new java.util.LinkedHashMap<>();
                for (int id : ids(c)) { SimData.Sim s = simOf(c, id, ss); if (s != null) use.put(SimData.key(s), s); }
                for (SimData.Sim s : use.values()) {
                    String j = Api.simgrupo(s, pr != null ? 8500 : 45000);  // 1º pedido do dia pode montar as tabelas no servidor
                    if (j != null && !SimData.rows(j).isEmpty()) Store.setSimData(c, SimData.key(s), j);
                }
                java.util.HashSet<String> keep = new java.util.HashSet<>(); for (SimData.Sim s : ss) keep.add(SimData.key(s));
                Store.pruneSims(c, keep);
                if (Updater.quietCheck(c, pr != null ? 5000 : 20000)) FavWidget.render(c);  // atualização de dados = confere a versão também
            } finally {
                if (token != 0 && Store.simLoading(c) == token) Store.setSimLoading(c, 0);
                render(c);
                if (pr != null) pr.finish();
            }
        }).start();
    }

    static synchronized void render(Context c) {
        AppWidgetManager m = AppWidgetManager.getInstance(c);
        int[] ids = ids(c);
        if (ids.length == 0) return;
        List<SimData.Sim> ss = SimData.sims(Store.sims(c));
        int flagsImm = PendingIntent.FLAG_UPDATE_CURRENT | PendingIntent.FLAG_IMMUTABLE;
        int flagsMut = PendingIntent.FLAG_UPDATE_CURRENT | (Build.VERSION.SDK_INT >= 31 ? PendingIntent.FLAG_MUTABLE : 0);
        for (int id : ids) {
            SimData.Sim s = simOf(c, id, ss);
            String key = SimData.key(s), data = s == null ? "{}" : Store.simData(c, key);
            List<SimData.Row> rows = SimData.rows(data);
            RemoteViews v = new RemoteViews(c.getPackageName(), R.layout.widget_sim);
            String nm = s == null ? c.getString(R.string.sim_widget_name) : s.name, selT = nm + (ss.size() > 1 ? "  ▾" : "");
            v.setTextViewText(R.id.s_sel, selT); v.setTextViewText(R.id.s_sel2, selT);
            if (ss.size() > 1) {  // seletor só com mais de um Grupo simulação (como o dos Favoritos)
                Intent pick = new Intent(c, PickerActivity.class).putExtra(AppWidgetManager.EXTRA_APPWIDGET_ID, id).putExtra(PickerActivity.EXTRA_SIM, true)
                        .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK | Intent.FLAG_ACTIVITY_MULTIPLE_TASK | Intent.FLAG_ACTIVITY_EXCLUDE_FROM_RECENTS);
                pick.setData(Uri.parse("jg://simpick/" + id));
                v.setOnClickPendingIntent(R.id.s_sel, PendingIntent.getActivity(c, 500 + id, pick, flagsImm));
                v.setOnClickPendingIntent(R.id.s_sel2, PendingIntent.getActivity(c, 500 + id, pick, flagsImm));
            } else { v.setOnClickPendingIntent(R.id.s_sel, openApp(c, s, null, 600 + id)); v.setOnClickPendingIntent(R.id.s_sel2, openApp(c, s, null, 600 + id)); }
            v.setOnClickPendingIntent(R.id.s_logo, openApp(c, null, null, 0)); v.setOnClickPendingIntent(R.id.s_brand, openApp(c, null, null, 0));
            boolean busy = System.currentTimeMillis() - Store.simLoading(c) < 90_000;
            long at = s == null ? 0 : Store.simAt(c, key);
            String up = busy ? c.getString(R.string.widget_loading) : at > 0 ? WidgetData.fetched(at, java.util.TimeZone.getDefault()) : "";
            v.setTextViewText(R.id.s_time, up);
            v.setViewVisibility(R.id.s_time, up.isEmpty() ? View.GONE : View.VISIBLE);
            // marca comprida "JG Investing" até o seletor (como no widget Favoritos) ou, com nome de grupo longo, o logo quadrado
            android.os.Bundle op = m.getAppWidgetOptions(id);
            android.content.res.Configuration cf = c.getResources().getConfiguration();
            int hw = WidgetData.widthDp(op.getInt(AppWidgetManager.OPTION_APPWIDGET_MIN_WIDTH, 0), op.getInt(AppWidgetManager.OPTION_APPWIDGET_MAX_WIDTH, 0),
                    cf.orientation == android.content.res.Configuration.ORIENTATION_LANDSCAPE);
            float dens = c.getResources().getDisplayMetrics().density;
            String bn = ss.size() > 1 ? nm : nm.substring(0, Math.max(0, nm.length() - 3));  // sem ▾ o chip é ~3 letras menor
            boolean brand = WidgetData.longLogo(bn, hw, Math.round(c.getResources().getDimension(R.dimen.brand_w) / dens), cf.fontScale, !up.isEmpty());
            v.setViewVisibility(R.id.s_brand, brand ? View.VISIBLE : View.GONE);
            v.setViewVisibility(R.id.s_sel2, brand ? View.VISIBLE : View.GONE);
            v.setViewVisibility(R.id.s_logo, brand ? View.GONE : View.VISIBLE);
            v.setViewVisibility(R.id.s_mid, brand ? View.GONE : View.VISIBLE);
            if (brand) {
                android.graphics.Bitmap bm = FavWidget.brandBitmap(c, Math.round((WidgetData.brandRoom(bn, hw, cf.fontScale, !up.isEmpty()) - 4) * dens), Math.round(30 * dens));
                if (bm != null) v.setImageViewBitmap(R.id.s_brand, bm);
            }
            String sub = s == null ? "" : "Desde " + s.di.substring(5) + "/" + s.di.substring(0, 4) + " · " + SimData.money(s.v0) + " em cada modelo";
            v.setTextViewText(R.id.s_sub, sub);
            v.setViewVisibility(R.id.s_sub, sub.isEmpty() ? View.GONE : View.VISIBLE);
            v.setTextViewText(R.id.s_empty, c.getString(s == null ? R.string.sim_empty : R.string.sim_wait));
            Intent rf = new Intent(c, SimWidget.class).setAction(ACTION_REFRESH);
            v.setOnClickPendingIntent(R.id.s_refresh, PendingIntent.getBroadcast(c, 11, rf, flagsImm));
            Intent tpl = new Intent(c, WidgetTap.class).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK | Intent.FLAG_ACTIVITY_NO_ANIMATION
                    | Intent.FLAG_ACTIVITY_EXCLUDE_FROM_RECENTS | Intent.FLAG_ACTIVITY_MULTIPLE_TASK);
            v.setPendingIntentTemplate(R.id.s_list, PendingIntent.getActivity(c, 12, tpl, flagsMut));
            v.setEmptyView(R.id.s_list, R.id.s_empty);
            if (Build.VERSION.SDK_INT >= 31) {
                RemoteViews.RemoteCollectionItems.Builder b = new RemoteViews.RemoteCollectionItems.Builder().setHasStableIds(true).setViewTypeCount(VIEW_TYPES);
                for (SimData.Item it : SimData.items(rows, openModel(c, s))) b.addItem(it.id(), item(c, s, it));
                v.setRemoteAdapter(R.id.s_list, b.build());
            } else {
                Intent svc = new Intent(c, SimWidgetService.class).putExtra(AppWidgetManager.EXTRA_APPWIDGET_ID, id);
                svc.setData(Uri.parse(svc.toUri(Intent.URI_INTENT_SCHEME)));
                legacyAdapter(v, svc);
            }
            m.updateAppWidget(id, v);
        }
        if (Build.VERSION.SDK_INT < 31) legacyNotify(m, ids);
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
            h.setOnClickFillInIntent(R.id.h_open, tap("so", sid, r.m));
            return h;
        }
        if (it.type == SimData.Item.POS || it.type == SimData.Item.CDB) {
            RemoteViews pv = new RemoteViews(c.getPackageName(), R.layout.widget_sim_pos);
            if (it.type == SimData.Item.CDB) {
                pv.setTextViewText(R.id.p_name, "Caixa no CDB"); pv.setViewVisibility(R.id.p_t, View.GONE);
                pv.setTextViewText(R.id.p_q, ""); pv.setTextViewText(R.id.p_inv, "");
                pv.setTextViewText(R.id.p_v, SimData.money(r.cash)); pv.setTextColor(R.id.p_v, c.getColor(R.color.c_txt));
                pv.setOnClickFillInIntent(R.id.p_row, tap("so", sid, r.m));
                return pv;
            }
            SimData.Pos p = it.pos; boolean nm = p.s != null && !p.s.isEmpty();
            pv.setTextViewText(R.id.p_name, nm ? p.s : p.t);
            pv.setTextViewText(R.id.p_t, nm ? p.t : "");
            pv.setViewVisibility(R.id.p_t, nm ? View.VISIBLE : View.GONE);
            pv.setTextViewText(R.id.p_q, SimData.qty(p.q));
            pv.setTextViewText(R.id.p_inv, SimData.money(p.inv));
            pv.setTextViewText(R.id.p_v, SimData.money(p.v));
            pv.setTextColor(R.id.p_v, c.getColor(p.v >= p.inv ? R.color.c_pos : R.color.c_neg));
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
