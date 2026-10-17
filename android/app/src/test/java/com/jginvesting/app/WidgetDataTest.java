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
        String j = "{\"u\":\"16/10/2026 22:41:57\",\"r\":[{\"t\":\"BBAS3\",\"p\":23.76,\"v\":-0.55,\"f\":13.8,\"m\":\"Gordon\"},"
                 + "{\"t\":\"PETR4\",\"p\":57.36,\"v\":4.04,\"f\":null,\"m\":null},{\"t\":\"XXXX9\"}]}";
        List<WidgetData.Item> it = WidgetData.items(Arrays.asList("PETR4", "BBAS3", "VALE3"), j);
        assertEquals(3, it.size());
        assertEquals("PETR4", it.get(0).t); assertNull(it.get(0).f); assertEquals(57.36, it.get(0).p, 1e-9);
        assertEquals("Gordon", it.get(1).m); assertEquals(13.8, it.get(1).f, 1e-9);
        assertEquals("VALE3", it.get(2).t); assertNull(it.get(2).p);
        assertEquals("16/10 22:41", WidgetData.updated(j));
        assertEquals(3, WidgetData.items(Arrays.asList("PETR4", "BBAS3", "VALE3"), "{}").size());
    }

    @Test public void formatsLikeTheSite() {
        assertEquals("R$ 1.234,56", WidgetData.price(1234.56));
        assertEquals("—", WidgetData.price(null));
        assertEquals("▲ 4,04%", WidgetData.change(4.04));
        assertEquals("▼ 0,55%", WidgetData.change(-0.55));
        assertEquals("Barato +43%", WidgetData.badge(43.3));
        assertEquals("Caro −75%", WidgetData.badge(-75.2));
        assertEquals("—", WidgetData.badge(null));
    }
}
