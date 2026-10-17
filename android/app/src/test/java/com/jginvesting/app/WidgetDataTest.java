package com.jginvesting.app;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertNull;

import java.util.Arrays;
import java.util.List;

import org.junit.Test;

public class WidgetDataTest {
    @Test public void favsKeepOrderAndDropInvalid() {
        assertEquals(Arrays.asList("PETR4", "BBAS3", "TAEE11"), WidgetData.favs("[\"petr4\",\"BBAS3\",\"PETR4\",\"<x>\",\"TAEE11\"]"));
        assertEquals(0, WidgetData.favs("lixo").size());
        assertEquals("PETR4,BBAS3", WidgetData.param(Arrays.asList("PETR4", "BBAS3")));
    }

    @Test public void itemsFollowFavoritesOrder() {
        String j = "{\"u\":\"16/10/2026 22:41:57\",\"gf\":[[25,\"Medo extremo\"],[45,\"Medo\"],[55,\"Neutro\"],[75,\"Ganância\"],[100,\"Ganância extrema\"]],"
                 + "\"r\":[{\"t\":\"BBAS3\",\"p\":23.76,\"v\":-0.55,\"f\":13.8,\"m\":\"Gordon\",\"g\":62},"
                 + "{\"t\":\"PETR4\",\"p\":57.36,\"v\":4.04,\"f\":null,\"m\":null},{\"t\":\"XXXX9\"}]}";
        List<WidgetData.Item> it = WidgetData.items(Arrays.asList("PETR4", "BBAS3", "VALE3"), j);
        assertEquals(3, it.size());
        assertEquals("PETR4", it.get(0).t); assertNull(it.get(0).f); assertEquals(57.36, it.get(0).p, 1e-9);
        assertEquals("Gordon", it.get(1).m); assertEquals(13.8, it.get(1).f, 1e-9);
        assertEquals("VALE3", it.get(2).t); assertNull(it.get(2).p);
        assertEquals("16/10 22:41", WidgetData.updated(j));
        assertEquals(3, WidgetData.items(Arrays.asList("PETR4", "BBAS3", "VALE3"), "{}").size());
        assertEquals(Integer.valueOf(62), it.get(1).g); assertNull(it.get(0).g);
        WidgetData.Bands b = WidgetData.bands(j);
        assertEquals(3, b.index(62)); assertEquals("Ganância", b.shortName(62));
        assertEquals(0, b.index(10)); assertEquals("Medo ext.", b.shortName(10));
        assertEquals(4, b.index(100)); assertEquals("Ganância ext.", b.shortName(90));
        assertEquals(2, b.index(55));
        assertEquals(0, WidgetData.bands("{}").lim.length);
    }

    @Test public void chartZonesAndTip() {
        // 11 pontos semanais a partir de 01/01/2024 00:00 (Brasília); base 10
        StringBuilder p = new StringBuilder();
        long t0 = 1704078000L;
        for (int i = 0; i <= 10; i++) p.append(i == 0 ? "" : ",").append("[").append(t0 + i * 604800L).append(",").append(10 + i).append("]");
        WidgetData.Chart ch = WidgetData.chart("{\"t\":\"PETR4\",\"b\":10,\"p\":[" + p + "]}");
        assertEquals(11, ch.size());
        assertEquals(0, WidgetData.zonePoint(ch, 0, 16));    // meio da 1ª faixa: ainda no 1º ponto
        assertEquals(10, WidgetData.zonePoint(ch, 15, 16));  // última faixa: último ponto
        assertEquals(5, WidgetData.zonePoint(ch, 8, 16));    // meio do gráfico
        for (int z = 1; z < 16; z++) assertEquals(true, WidgetData.zonePoint(ch, z, 16) >= WidgetData.zonePoint(ch, z - 1, 16));
        assertEquals("01/01/2024 · R$ 10,00 · +0,00%", WidgetData.tip(ch, 0));
        assertEquals("11/03/2024 · R$ 20,00 · +100,00%", WidgetData.tip(ch, 10));
        WidgetData.Chart dn = WidgetData.chart("{\"b\":20,\"p\":[[1704078000,20],[1704682800,15]]}");
        assertEquals("08/01/2024 · R$ 15,00 · -25,00%", WidgetData.tip(dn, 1));
        assertNull(WidgetData.chart("{}"));
        assertNull(WidgetData.chart("{\"b\":null,\"p\":[[1,2],[3,4]]}"));
        assertEquals(5.0, ChartDraw.niceStep(4.2), 1e-9);
        assertEquals(2.5, ChartDraw.niceStep(2.3), 1e-9);
    }

    @Test public void formatsLikeTheSite() {
        assertEquals("R$ 1.234,56", WidgetData.price(1234.56));
        assertEquals("—", WidgetData.price(null));
        assertEquals("▲ 4,04%", WidgetData.change(4.04));
        assertEquals("▼ 0,55%", WidgetData.change(-0.55));
        assertEquals("+43%", WidgetData.badge(43.3));
        assertEquals("−75%", WidgetData.badge(-75.2));
        assertEquals("—", WidgetData.change(null));
        assertEquals("—", WidgetData.badge(null));
    }
}
