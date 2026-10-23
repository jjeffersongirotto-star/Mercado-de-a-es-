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
        if ("sx".equals(a) || "so".equals(a) || "sp".equals(a)) {  // widget Grupo simulação: abrir/fechar as posições do modelo ou abrir as movimentações no app
            String sim = i.getStringExtra(SimWidget.EXTRA_SIM), mid = i.getStringExtra(SimWidget.EXTRA_MODEL);
            if (sim != null && SimData.validModel(mid)) {
                if ("so".equals(a) || "sp".equals(a)) {  // sp: janela só com a empresa (tk) dentro do modelo
                    String tk = "sp".equals(a) ? i.getStringExtra(SimWidget.EXTRA_TK) : null;
                    Intent o = new Intent(this, MainActivity.class).putExtra(SimWidget.EXTRA_SIM, sim).putExtra(SimWidget.EXTRA_MODEL, mid)
                            .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK | Intent.FLAG_ACTIVITY_SINGLE_TOP);
                    if (tk != null && WidgetData.validTicker(tk)) o.putExtra(SimWidget.EXTRA_TK, tk);
                    startActivity(o);
                } else {
                    String k = sim + "|" + mid;
                    Store.setSimExp(this, k.equals(Store.simExp(this)) ? "" : k);
                    SimWidget.render(this);
                }
            }
            finish(); overridePendingTransition(0, 0); return;
        }
        if (t != null && WidgetData.validTicker(t)) {
            if ("o".equals(a)) {
                startActivity(new Intent(this, MainActivity.class).putExtra(FavWidget.EXTRA_TICKER, t)
                        .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK | Intent.FLAG_ACTIVITY_SINGLE_TOP));
            } else if ("c".equals(a)) {  // 1.25: "Sem conexão, toque para tentar de novo"
                sendBroadcast(new Intent(this, FavWidget.class).setAction(FavWidget.ACTION_CHART).putExtra(FavWidget.EXTRA_TICKER, t));
            } else if ("z".equals(a)) {
                Store.setZone(this, i.getIntExtra(Z, -1));
                FavWidget.render(this);
            } else {
                boolean open = !t.equals(Store.expanded(this));
                Store.setExpanded(this, open ? t : "");
                FavWidget.render(this);
                // 1.23: a busca do gráfico vai num broadcast (goAsync), não numa thread desta tela, que fecha já
                if (open) sendBroadcast(new Intent(this, FavWidget.class).setAction(FavWidget.ACTION_CHART).putExtra(FavWidget.EXTRA_TICKER, t));
            }
        }
        finish();
        overridePendingTransition(0, 0);
    }
}
