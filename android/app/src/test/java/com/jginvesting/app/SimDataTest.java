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
        assertEquals("+ 29 empresas · R$ 236,99 no CDB", SimData.rest(b));
        assertNull(r.get(1).dp); assertEquals("—", SimData.dayPct(r.get(1).dp));
        assertTrue(SimData.rows("{}").isEmpty());
    }
}
