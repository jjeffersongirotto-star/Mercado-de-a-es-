package com.jginvesting.app;

import org.junit.Test;

import java.util.List;

import static org.junit.Assert.*;

public class SimDataTest {
    @Test public void gruposDoSiteValidos() {
        List<SimData.Sim> s = SimData.sims("[{\"id\":\"Barsi 2025\",\"n\":\"Barsi 2025\",\"di\":\"2025-03\",\"v0\":12000},"
                + "{\"id\":\"x\",\"di\":\"2025\",\"v0\":1},{\"id\":\"y\",\"di\":\"2024-01\",\"v0\":0},{\"id\":\"Barsi 2025\",\"di\":\"2024-01\",\"v0\":5}]");
        assertEquals(1, s.size());
        assertEquals("di=2025-03&v0=12000", SimData.query(s.get(0)));
        SimData.Sim f = SimData.sims("[{\"id\":\"G\",\"di\":\"2025-03\",\"v0\":12000,\"f\":{\"ap\":500,\"ex\":[],\"ret\":[]}}]").get(0);
        assertTrue(SimData.query(f).startsWith("di=2025-03&v0=12000&f=%7B"));
        assertEquals(" + R$ 500,00/mês", SimData.monthly(f));
        // data inicial com dia (Previsão desde 10/2026): o widget aceita e mostra DD/MM/AAAA; grupos antigos seguem MM/AAAA
        SimData.Sim dd = SimData.sims("[{\"id\":\"G\",\"di\":\"2025-04-07\",\"v0\":22000}]").get(0);
        assertEquals("di=2025-04-07&v0=22000", SimData.query(dd));
        assertEquals("07/04/2025", SimData.since(dd.di)); assertEquals("03/2025", SimData.since("2025-03"));
        assertTrue(SimData.sims("[{\"id\":\"G\",\"di\":\"2025-04-7\",\"v0\":1}]").isEmpty());
        assertEquals("Simulação 03-2025 2026-10-18.xlsx", SimData.fileName("Simulação 03/2025", "2026-10-18"));  // planilha do ⬇
        assertEquals("Grupo simulação 2026-10-18.xlsx", SimData.fileName("  ", "2026-10-18"));
        // linhas inteiras ao diminuir o widget: N linhas de modelo esticadas até a borda (nunca meia linha); aberto = linha base
        float d = 2.75f; float hdr = SimData.headerDp(1f, true);
        for (int hDp = 150; hDp <= 600; hDp += 7) {
            int listPx = Math.round((hDp - hdr) * d), rp = SimData.rowPx(hDp, d, 1f, true, 9, false), div = Math.round(d);
            int n = Math.max(1, (listPx + div) / (Math.round(46 * d) + div));
            assertTrue(rp >= Math.round(46 * d));
            if (n < 9 && listPx >= Math.round(46 * d)) assertTrue("h=" + hDp, Math.abs(n * rp + (n - 1) * div - listPx) <= n || rp == Math.round(Math.round(46 * d) * 1.6f));  // termina rente à borda (ou no teto de 1,6×, com espaço vazio — nunca meia linha)
        }
        assertEquals(Math.round(46 * d), SimData.rowPx(400, d, 1f, true, 9, true));
        assertEquals(0, SimData.rowPx(0, d, 1f, true, 9, false)); assertEquals("", SimData.monthly(s.get(0)));  // aporte mensal vai junto (1.17+)
        assertNotEquals(SimData.key(s.get(0)).replace("Barsi 2025", "G"), SimData.key(f));
        assertSame(s.get(0), SimData.pick("sumiu", s));  // grupo apagado: mostra o primeiro
        assertNull(SimData.pick("", SimData.sims("[]")));
        assertTrue(SimData.sims("lixo").isEmpty());
        assertNotEquals(SimData.key(s.get(0)), SimData.key(SimData.sims("[{\"id\":\"Barsi 2025\",\"di\":\"2025-04\",\"v0\":12000}]").get(0)));
    }

    @Test public void linhasEPosicoes() {
        String j = "{\"r\":[{\"m\":\"barsi\",\"n\":\"Método Barsi\",\"ap\":12000,\"v\":17161.64,\"dv\":-36.95,\"dp\":-0.21,\"cash\":236.99,\"np\":30,"
                + "\"pos\":[{\"t\":\"CEBR5\",\"s\":\"CEB\",\"q\":99,\"inv\":1871.46,\"v\":2489.85},{\"t\":\"bad ticker\",\"q\":1,\"inv\":1,\"v\":1}]},"
                + "{\"m\":\"x;rm\",\"n\":\"?\"},{\"m\":\"cdb\",\"n\":\"CDB\",\"ap\":12000,\"v\":14000,\"dv\":0,\"dp\":null,\"cash\":14000,\"np\":0,\"pos\":[]}]}";
        List<SimData.Row> r = SimData.rows(j);
        assertEquals(2, r.size());
        SimData.Row b = r.get(0);
        assertEquals("Método Barsi", b.n); assertEquals(1, b.pos.size()); assertEquals(99, b.pos.get(0).q);
        assertEquals("R$ 12.000", SimData.money(b.ap)); assertEquals("R$ 17.162", SimData.money(b.v)); assertEquals("R$ 950,40", SimData.money(950.4));
        assertEquals("▼ 0,21%", SimData.dayPct(b.dp)); assertEquals("−R$ 36,95", SimData.dayMoney(b.dv));
        assertEquals("+43,0%", SimData.total(b.v, b.ap));
        // lista plana: só o modelo aberto mostra título, TODAS as empresas (sem "+ N empresas") e o CDB no fim
        List<SimData.Item> it = SimData.items(r, "barsi");
        assertEquals(5, it.size());
        assertEquals(SimData.Item.HEAD, it.get(1).type); assertEquals(SimData.Item.POS, it.get(2).type); assertEquals("CEBR5", it.get(2).pos.t);
        assertEquals(SimData.Item.CDB, it.get(3).type); assertEquals(SimData.Item.ROW, it.get(4).type);
        assertEquals(2, SimData.items(r, "").size());
        assertEquals(56, SimData.empDp(b));  // nome curto: só o mínimo
        b.pos.add(new SimData.Pos("TAEE11", "Transmissora Aliança de Energia", 1, 1, 1)); assertEquals(112, SimData.empDp(b));  // longo: teto (quebra em 2 linhas)
        java.util.HashSet<Long> ids = new java.util.HashSet<>(); for (SimData.Item x : it) ids.add(x.id()); assertEquals(5, ids.size());
        assertNull(r.get(1).dp); assertEquals("—", SimData.dayPct(r.get(1).dp));
        assertTrue(SimData.rows("{}").isEmpty());
    }
}
