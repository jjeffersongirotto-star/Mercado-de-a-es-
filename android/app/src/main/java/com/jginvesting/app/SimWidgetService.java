package com.jginvesting.app;

import android.content.Context;
import android.content.Intent;
import android.widget.RemoteViews;
import android.widget.RemoteViewsService;

import java.util.ArrayList;
import java.util.List;

/** Linhas do widget Grupo simulação no Android 7 a 11 (no 12+ o SimWidget entrega as linhas direto). */
public class SimWidgetService extends RemoteViewsService {
    @Override public RemoteViewsFactory onGetViewFactory(Intent intent) {
        final Context c = getApplicationContext();
        return new RemoteViewsFactory() {
            List<SimData.Item> rows = new ArrayList<>();
            SimData.Sim s;
            public void onCreate() { }
            public void onDataSetChanged() {
                int id = intent.getIntExtra(android.appwidget.AppWidgetManager.EXTRA_APPWIDGET_ID, 0);
                s = SimWidget.simOf(c, id, SimData.sims(Store.sims(c)));
                rows = s == null ? new ArrayList<>() : SimData.items(SimData.rows(Store.simData(c, SimData.key(s))), SimWidget.openModel(c, s));
            }
            public void onDestroy() { }
            public int getCount() { return rows.size(); }
            public RemoteViews getViewAt(int i) { return SimWidget.item(c, s, rows.get(i)); }
            public RemoteViews getLoadingView() { return null; }
            public int getViewTypeCount() { return SimWidget.VIEW_TYPES; }
            public long getItemId(int i) { return rows.get(i).id(); }
            public boolean hasStableIds() { return true; }
        };
    }
}
