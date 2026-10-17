package com.jginvesting.app;

import android.app.Activity;
import android.content.Intent;
import android.os.Bundle;

/** Toque numa linha do widget (sem tela): abre/fecha o gráfico, marca um ponto ou abre o app na ação. */
public class WidgetTap extends Activity {
    static final String A = "a", T = "t", Z = "z";

    @Override protected void onCreate(Bundle b) {
        super.onCreate(b);
        Intent i = getIntent();
        String a = i.getStringExtra(A), t = i.getStringExtra(T);
        if (t != null && WidgetData.validTicker(t)) {
            if ("o".equals(a)) {
                startActivity(new Intent(this, MainActivity.class).putExtra(FavWidget.EXTRA_TICKER, t)
                        .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK | Intent.FLAG_ACTIVITY_SINGLE_TOP));
            } else if ("z".equals(a)) {
                Store.setZone(this, i.getIntExtra(Z, -1));
                FavWidget.render(this);
            } else {
                boolean open = !t.equals(Store.expanded(this));
                Store.setExpanded(this, open ? t : "");
                FavWidget.render(this);
                if (open) FavWidget.chartAsync(this, t);
            }
        }
        finish();
        overridePendingTransition(0, 0);
    }
}
