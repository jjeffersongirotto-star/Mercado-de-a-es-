package com.jginvesting.app;

import android.content.Context;
import android.graphics.Bitmap;
import android.graphics.Canvas;
import android.graphics.DashPathEffect;
import android.graphics.Paint;
import android.graphics.Path;

import java.text.SimpleDateFormat;
import java.util.Date;
import java.util.Locale;
import java.util.TimeZone;

/** Desenha o gráfico de 5 anos do widget com as cores do gráfico do site (grafico.js e .gc-* do index.html, lidas no build). */
final class ChartDraw {
    private ChartDraw() { }

    /** Passo "redondo" das linhas de grade (1, 2, 2,5 ou 5 × 10^n), como no gráfico do site. */
    static double niceStep(double raw) {
        if (!(raw > 0)) return 1;
        double p = Math.pow(10, Math.floor(Math.log10(raw))), m = raw / p;
        return (m <= 1 ? 1 : m <= 2 ? 2 : m <= 2.5 ? 2.5 : m <= 5 ? 5 : 10) * p;
    }

    /** sel = ponto marcado (linha vertical e ponto) ou -1. */
    /** dp = pixels por dp do bitmap (o widget o estica para o tamanho real). RGB_565 sobre o fundo do widget: bitmap pequeno
     *  (o Android limita a ~1 MB o que vai para a tela inicial de uma vez). */
    static Bitmap draw(Context c, WidgetData.Chart ch, int wPx, int hPx, int sel, float dp) {
        Bitmap b = Bitmap.createBitmap(Math.max(wPx, 50), Math.max(hPx, 30), Bitmap.Config.RGB_565);
        Canvas cv = new Canvas(b);
        cv.drawColor(c.getColor(R.color.bg_in));
        int n = ch.size();
        double y0 = Double.MAX_VALUE, y1 = -Double.MAX_VALUE;
        for (double v : ch.c) { y0 = Math.min(y0, v); y1 = Math.max(y1, v); }
        y0 = Math.min(y0, ch.base); y1 = Math.max(y1, ch.base);
        double mn = ch.base * 0.005; if (y1 - y0 < mn) { y0 -= mn / 2; y1 += mn / 2; }
        double yr = (y1 - y0) * 0.06; y0 -= yr; y1 += yr;
        float left = 40 * dp, right = b.getWidth() - 2 * dp, top = 2 * dp, bottom = b.getHeight() - 13 * dp;
        long x0 = ch.t[0], x1 = ch.t[n - 1];
        final double fy0 = y0, fy1 = y1;
        java.util.function.LongFunction<Float> X = (t) -> (float) (left + (t - x0) / (double) Math.max(1, x1 - x0) * (right - left));
        java.util.function.DoubleFunction<Float> Y = (v) -> (float) (bottom - (v - fy0) / (fy1 - fy0) * (bottom - top));

        Paint grid = new Paint(Paint.ANTI_ALIAS_FLAG); grid.setColor(c.getColor(R.color.bd)); grid.setAlpha(128); grid.setStrokeWidth(dp);
        Paint lab = new Paint(Paint.ANTI_ALIAS_FLAG); lab.setColor(c.getColor(R.color.c_dim)); lab.setTextSize(9.5f * dp);
        double step = niceStep((y1 - y0) / 4);
        lab.setTextAlign(Paint.Align.RIGHT);
        for (double v = Math.ceil(y0 / step) * step; v <= y1; v += step) {
            float y = Y.apply(v); cv.drawLine(left, y, right, y, grid);
            cv.drawText(WidgetData.axis(v, ch.cur), left - 3 * dp, y + 3.5f * dp, lab);
        }
        Paint zero = new Paint(Paint.ANTI_ALIAS_FLAG); zero.setColor(c.getColor(R.color.c_mut)); zero.setAlpha(153); zero.setStrokeWidth(dp);
        zero.setStyle(Paint.Style.STROKE); zero.setPathEffect(new DashPathEffect(new float[]{4 * dp, 3 * dp}, 0));
        Path zp = new Path(); zp.moveTo(left, Y.apply(ch.base)); zp.lineTo(right, Y.apply(ch.base)); cv.drawPath(zp, zero);  // preço no início

        SimpleDateFormat mf = new SimpleDateFormat("MM/yy", Locale.ROOT); mf.setTimeZone(TimeZone.getTimeZone("America/Sao_Paulo"));
        float ly = b.getHeight() - 2 * dp;
        lab.setTextAlign(Paint.Align.LEFT); cv.drawText(mf.format(new Date(x0 * 1000)), left, ly, lab);
        lab.setTextAlign(Paint.Align.CENTER); cv.drawText(mf.format(new Date((x0 + x1) / 2 * 1000)), (left + right) / 2, ly, lab);
        lab.setTextAlign(Paint.Align.RIGHT); cv.drawText(mf.format(new Date(x1 * 1000)), right, ly, lab);

        Paint line = new Paint(Paint.ANTI_ALIAS_FLAG); line.setColor(c.getColor(R.color.chart_stock)); line.setStrokeWidth(2.4f * dp);
        line.setStyle(Paint.Style.STROKE); line.setStrokeJoin(Paint.Join.ROUND);
        Path p = new Path();
        for (int i = 0; i < n; i++) { float x = X.apply(ch.t[i]), y = Y.apply(ch.c[i]); if (i == 0) p.moveTo(x, y); else p.lineTo(x, y); }
        cv.drawPath(p, line);

        if (sel >= 0 && sel < n) {  // mira: linha vertical tracejada e ponto (como .gc-vl e .gc-dot)
            float x = X.apply(ch.t[sel]), y = Y.apply(ch.c[sel]);
            Paint vl = new Paint(zero); vl.setAlpha(178);
            Path vp = new Path(); vp.moveTo(x, top); vp.lineTo(x, bottom); cv.drawPath(vp, vl);
            Paint ring = new Paint(Paint.ANTI_ALIAS_FLAG); ring.setColor(c.getColor(R.color.bg_in)); cv.drawCircle(x, y, 6 * dp, ring);
            Paint dot = new Paint(Paint.ANTI_ALIAS_FLAG); dot.setColor(c.getColor(R.color.chart_stock)); cv.drawCircle(x, y, 4 * dp, dot);
        }
        return b;
    }
}
