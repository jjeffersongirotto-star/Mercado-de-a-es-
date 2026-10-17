package com.jginvesting.app;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertNull;
import static org.junit.Assert.assertFalse;
import static org.junit.Assert.assertTrue;

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

    @Test public void groupsAndSelection() {
        String g = "[{\"id\":\"pre:valor\",\"n\":\"Maior valorização (1 ano)\",\"t\":[\"PETR4\",\"vale3\"]},"
                 + "{\"id\":\"user:Bancos\",\"n\":\"Bancos\",\"t\":[\"ITUB4\",\"BBAS3\",\"ITUB4\"]},"
                 + "{\"id\":\"vazio\",\"n\":\"Vazio\",\"t\":[]},{\"id\":\"fav\",\"n\":\"x\",\"t\":[\"A1B2\"]}]";
        List<WidgetData.Group> gs = WidgetData.groups(g);
        assertEquals(2, gs.size());                                   // vazio e "fav" ficam de fora
        assertEquals(Arrays.asList("PETR4", "VALE3"), WidgetData.tickers("pre:valor", "[]", gs));
        assertEquals(Arrays.asList("ITUB4", "BBAS3"), WidgetData.tickers("user:Bancos", "[]", gs));
        assertEquals(Arrays.asList("WEGE3"), WidgetData.tickers("fav", "[\"WEGE3\"]", gs));
        assertEquals(0, WidgetData.tickers("user:Apagado", "[\"WEGE3\"]", gs).size());
        assertEquals("Maior valorização (1 ano)", WidgetData.name("pre:valor", gs));
        assertEquals("Favoritos", WidgetData.name("fav", gs));
        assertEquals(true, WidgetData.exists("fav", gs)); assertEquals(false, WidgetData.exists("user:Apagado", gs));
        StringBuilder many = new StringBuilder("[");
        for (int i = 0; i < 60; i++) many.append(i == 0 ? "" : ",").append("\"T").append(1000 + i).append("\"");
        assertEquals(WidgetData.MAX_ROWS, WidgetData.tickers("fav", many + "]", gs).size());
        assertEquals(0, WidgetData.groups("lixo").size());
    }

    @Test public void logoNameAndInitials() {
        String j = "{\"r\":[{\"t\":\"ITUB4\",\"s\":\"Itau Unibanco\",\"l\":\"9fa9da007cc7.png\",\"p\":38.5},"
                 + "{\"t\":\"ITUB3\",\"s\":\"Itau Unibanco\",\"l\":\"9fa9da007cc7.png\"},"
                 + "{\"t\":\"NATU3\",\"s\":\"Natura\",\"l\":null},{\"t\":\"XPTO3\",\"l\":\"../../x.png\"}]}";
        List<WidgetData.Item> it = WidgetData.items(Arrays.asList("ITUB4", "ITUB3", "NATU3", "XPTO3", "SEMD3"), j);
        assertEquals("Itau Unibanco", it.get(0).s);
        assertEquals("9fa9da007cc7.png", it.get(0).l);
        assertEquals(null, it.get(2).l);                     // sem logo: iniciais
        assertEquals(null, it.get(3).l);                     // nome de arquivo inválido é ignorado
        assertEquals(null, it.get(4).s);                     // ticker sem dados
        assertEquals(Arrays.asList("9fa9da007cc7.png"), WidgetData.logos(it));  // mesmo logo baixado uma vez
        assertEquals("NA", WidgetData.initials("NATU3"));
    }

    @Test public void bitmapBudgetUnderOneMegabyte() {
        for (float d : new float[]{1f, 2f, 2.75f, 3.5f, 4f})
            for (int rows : new int[]{1, 10, 24, 25, WidgetData.MAX_ROWS})
                assertEquals(true, WidgetData.bitmapBytes(rows, d, 600) < 1_000_000L);
        assertEquals(56, WidgetData.logoPx(2.75f, 10));
        assertEquals(44, WidgetData.logoPx(2.75f, 40));
        assertEquals(32, WidgetData.logoPx(1f, 10));
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

    @Test public void shortAndDottedTickersKept() {  // 1.5 descartava KO, V, GE, F, BRK.B e RR. (regra antiga: 3 a 12 letras/dígitos)
        assertEquals(Arrays.asList("KO", "V", "GE", "F", "BRK.B", "RR.", "BT-A", "7203", "PETR4"),
                WidgetData.favs("[\"ko\",\"V\",\"GE\",\"F\",\"BRK.B\",\"RR.\",\"BT-A\",\"7203\",\"PETR4\",\"KO\"]"));
        for (String bad : new String[]{"", ".X", "-A", "A B", "A'B", "<x>", "ABCDEFGHIJKLM", "A/B", "javascript:"})
            assertFalse(bad, WidgetData.validTicker(bad));
        assertEquals(1, WidgetData.groups("[{\"id\":\"g1\",\"n\":\"EUA\",\"t\":[\"KO\",\"BRK.B\"]}]").size());
        assertEquals(Arrays.asList("KO", "BRK.B"), WidgetData.groups("[{\"id\":\"g1\",\"n\":\"EUA\",\"t\":[\"KO\",\"BRK.B\"]}]").get(0).t);
    }

    @Test public void foreignPriceInOwnCurrency() {
        String j = "{\"r\":[{\"t\":\"KO\",\"p\":93.9,\"v\":2.07,\"c\":\"USD\",\"f\":null,\"g\":null},"
                + "{\"t\":\"7203\",\"p\":3094,\"v\":-1.5,\"c\":\"JPY\"},{\"t\":\"PETR4\",\"p\":30.5,\"v\":1}]}";
        java.util.List<WidgetData.Item> it = WidgetData.items(Arrays.asList("KO", "7203", "PETR4", "AAPL34"), j);
        assertEquals("US$ 93,90", WidgetData.price(it.get(0).p, it.get(0).c));
        assertEquals("¥ 3.094", WidgetData.price(it.get(1).p, it.get(1).c));
        assertEquals("R$ 30,50", WidgetData.price(it.get(2).p, it.get(2).c));
        assertEquals("—", WidgetData.price(it.get(3).p, it.get(3).c));
        assertEquals("—", WidgetData.badge(it.get(0).f));
        assertNull(it.get(0).g);
        assertEquals("£ 13,51", WidgetData.price(13.506, "GBP"));
        assertEquals("€ 199,22", WidgetData.price(199.22, "EUR"));
        assertEquals("US$ 12.345", WidgetData.price(12345.4, "USD"));     // compacto: sem centavos de 10 mil para cima
        assertEquals("US$ 1,07 mi", WidgetData.price(1070000.0, "USD"));  // BRK.A
        assertNull(WidgetData.cur("usd")); assertNull(WidgetData.cur("<b>"));
    }

    @Test public void foreignChartTipAndAxis() {
        WidgetData.Chart ch = WidgetData.chart("{\"t\":\"KO\",\"b\":50,\"c\":\"USD\",\"p\":[[1700000000,50],[1760000000,93.9]]}");
        assertEquals("USD", ch.cur);
        assertTrue(WidgetData.tip(ch, 1).contains("US$ 93,90"));
        assertEquals("340", WidgetData.axis(340.0, "USD"));
        assertEquals("R$ 60,00", WidgetData.axis(60.0, null));
        assertNull(WidgetData.chart("{\"t\":\"PETR4\",\"b\":10,\"p\":[[1,10],[2,11]]}").cur);
    }
}
