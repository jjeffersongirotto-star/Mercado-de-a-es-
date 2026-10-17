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
            public void onCreate() { }
            public void onDataSetChanged() { items = WidgetData.items(WidgetData.favs(Store.favs(c)), Store.data(c)); }
            public void onDestroy() { }
            public int getCount() { return items.size(); }
            public RemoteViews getViewAt(int i) { return FavWidget.row(c, items.get(i)); }
            public RemoteViews getLoadingView() { return null; }
            public int getViewTypeCount() { return 1; }
            public long getItemId(int i) { return items.get(i).t.hashCode(); }
            public boolean hasStableIds() { return true; }
        };
    }
}
