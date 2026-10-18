package com.jginvesting.app;

import android.app.Activity;
import android.app.AlertDialog;
import android.appwidget.AppWidgetManager;
import android.os.Bundle;

import java.util.List;

/** Seletor do widget (toque em "Favoritos ▾"): Favoritos ou um grupo da aba Grupos; a escolha fica guardada em cada widget. */
public class PickerActivity extends Activity {
    static final String EXTRA_SIM = "sim";

    @Override protected void onCreate(Bundle b) {
        super.onCreate(b);
        final int id = getIntent().getIntExtra(AppWidgetManager.EXTRA_APPWIDGET_ID, AppWidgetManager.INVALID_APPWIDGET_ID);
        if (getIntent().getBooleanExtra(EXTRA_SIM, false)) { simPicker(id); return; }
        final List<WidgetData.Group> gs = WidgetData.groups(Store.groups(this));
        String[] names = new String[gs.size() + 1];
        names[0] = WidgetData.FAV_NAME;
        for (int i = 0; i < gs.size(); i++) names[i + 1] = gs.get(i).name;
        String cur = FavWidget.selOf(this, id, gs);
        int checked = 0;
        for (int i = 0; i < gs.size(); i++) if (gs.get(i).id.equals(cur)) checked = i + 1;
        AlertDialog.Builder d = new AlertDialog.Builder(this, AlertDialog.THEME_DEVICE_DEFAULT_DARK)
                .setTitle("Mostrar no widget")
                .setSingleChoiceItems(names, checked, (dlg, w) -> {
                    Store.setSel(this, id, w == 0 ? WidgetData.FAV : gs.get(w - 1).id);
                    Store.setExpanded(this, "");
                    // mesmo caminho do ⟳ (broadcast com goAsync: o Android não congela a busca quando o seletor fecha)
                    sendBroadcast(new android.content.Intent(this, FavWidget.class).setAction(FavWidget.ACTION_REFRESH));
                    dlg.dismiss();
                })
                .setOnDismissListener(x -> { finish(); overridePendingTransition(0, 0); });
        if (gs.isEmpty()) d.setMessage("Abra o app uma vez para carregar os grupos da aba Grupos.");
        d.show();
    }

    /** Widget Grupo simulação: escolhe qual Grupo simulação mostrar (só aparece com mais de um). */
    private void simPicker(int id) {
        final List<SimData.Sim> ss = SimData.sims(Store.sims(this));
        String[] names = new String[ss.size()];
        for (int i = 0; i < ss.size(); i++) names[i] = ss.get(i).name;
        SimData.Sim cur = SimWidget.simOf(this, id, ss);
        int checked = cur == null ? -1 : ss.indexOf(cur);
        new AlertDialog.Builder(this, AlertDialog.THEME_DEVICE_DEFAULT_DARK)
                .setTitle("Mostrar no widget")
                .setSingleChoiceItems(names, checked, (dlg, w) -> {
                    Store.setSimSel(this, id, ss.get(w).id);
                    sendBroadcast(new android.content.Intent(this, SimWidget.class).setAction(SimWidget.ACTION_REFRESH));
                    dlg.dismiss();
                })
                .setOnDismissListener(x -> { finish(); overridePendingTransition(0, 0); })
                .show();
    }
}
