package com.jginvesting.app;

import android.content.Context;
import android.content.Intent;
import android.widget.RemoteViews;
import android.widget.RemoteViewsService;

import java.util.ArrayList;
import java.util.List;

/** Linhas do widget no Android 7 a 11 (no 12+ o FavWidget entrega as linhas direto). */
public class WidgetService extends RemoteViewsService {
    @Override public RemoteViewsFactory onGetViewFactory(Intent intent) {
        final Context c = getApplicationContext();
        return new RemoteViewsFactory() {
            List<WidgetData.Item> items = new ArrayList<>();
            WidgetData.Bands bands = WidgetData.bands("{}");
            int wDp = 300;
            public void onCreate() { }
            public void onDataSetChanged() {
                int id = intent.getIntExtra(android.appwidget.AppWidgetManager.EXTRA_APPWIDGET_ID, 0);
                List<WidgetData.Group> gs = WidgetData.groups(Store.groups(c));
                String sel = FavWidget.selOf(c, id, gs), data = Store.data(c, sel);
                items = WidgetData.items(WidgetData.tickers(sel, Store.favs(c), gs), data); bands = WidgetData.bands(data);
                wDp = android.appwidget.AppWidgetManager.getInstance(c).getAppWidgetOptions(id).getInt(android.appwidget.AppWidgetManager.OPTION_APPWIDGET_MIN_WIDTH, 300);
            }
            public void onDestroy() { }
            public int getCount() { return items.size(); }
            public RemoteViews getViewAt(int i) { return FavWidget.row(c, items.get(i), bands, wDp); }
            public RemoteViews getLoadingView() { return null; }
            public int getViewTypeCount() { return 1; }
            public long getItemId(int i) { return items.get(i).t.hashCode(); }
            public boolean hasStableIds() { return true; }
        };
    }
}
