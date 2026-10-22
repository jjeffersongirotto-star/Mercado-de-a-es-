package com.jginvesting.app;

import android.app.job.JobInfo;
import android.app.job.JobParameters;
import android.app.job.JobScheduler;
import android.app.job.JobService;
import android.content.ComponentName;
import android.content.Context;
import android.os.PersistableBundle;

/** ⟳ do widget: o mesmo POST /api/refresh do ⟳ do site (com src=widget: o servidor só refaz com dados de mais de 10 min no pregão,
 *  uma atualização por vez, sem limpar as ações de fora), espera ela terminar consultando /api/status (leve) e busca /api/widget.
 *  JobService porque a espera passa do limite de ~10 s do broadcast. */
public class RefreshJob extends JobService {
    static final int ID = 7701;
    static final long WAIT_MS = 120_000, POLL_MS = 4_000;

    static boolean schedule(Context c, long token) {
        try {
            PersistableBundle b = new PersistableBundle(); b.putLong("tk", token);
            JobInfo j = new JobInfo.Builder(ID, new ComponentName(c, RefreshJob.class)).setOverrideDeadline(0).setExtras(b).build();
            JobScheduler s = (JobScheduler) c.getSystemService(Context.JOB_SCHEDULER_SERVICE);
            return s != null && s.schedule(j) == JobScheduler.RESULT_SUCCESS;
        } catch (Exception e) { return false; }
    }

    @Override public boolean onStartJob(JobParameters p) {
        final Context c = getApplicationContext();
        final long tk = p.getExtras().getLong("tk", 0);
        new Thread(() -> {
            try {
                if (WidgetData.refreshing(Api.refresh(10_000))) {  // servidor refazendo: espera (com limite), "Atualizando…" na tela
                    long end = System.currentTimeMillis() + WAIT_MS;
                    while (System.currentTimeMillis() < end) {
                        try { Thread.sleep(POLL_MS); } catch (InterruptedException e) { break; }
                        String st = Api.status(8_000);
                        if (st != null && !WidgetData.refreshing(st)) break;
                    }
                }
                FavWidget.refreshNow(c, null, tk);  // protegido: erro do launcher não deixa o job sem fim
            } catch (RuntimeException e) {
                Widgets.log("RefreshJob", e);
                if (tk != 0 && Store.endLoading(c, tk)) FavWidget.render(c);
            } finally { jobFinished(p, false); }
        }).start();
        return true;
    }

    @Override public boolean onStopJob(JobParameters p) { return false; }
}
