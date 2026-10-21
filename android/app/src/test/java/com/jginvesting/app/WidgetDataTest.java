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
            for (int rows : new int[]{1, 10, 12, 13, 24, 25, WidgetData.MAX_ROWS})
                assertEquals(true, WidgetData.bitmapBytes(rows, d, 600) < 1_000_000L);
        assertEquals(88, WidgetData.logoPx(2.75f, 10));
        assertEquals(96, WidgetData.logoPx(3.5f, 12));
        assertEquals(64, WidgetData.logoPx(3.5f, 20));
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
        assertEquals("Prej.", WidgetData.badge(null, "Prej."));
        assertEquals("s/ VJ", WidgetData.badge(null, "s/ VJ"));
        assertEquals("—", WidgetData.badge(null, "Prejuízo recorrente"));  // longo demais para o chip
        assertEquals("+43%", WidgetData.badge(43.3, "Prej."));
        assertEquals("0%", WidgetData.badge(-0.2));  // AURE3: era "−0%" vermelho
        assertEquals("0%", WidgetData.badge(0.0));
        assertTrue(WidgetData.up(-0.2)); assertFalse(WidgetData.up(-0.6)); assertTrue(WidgetData.up(0.0));
        assertEquals("−1%", WidgetData.badge(-0.6));
        assertEquals("+3%", WidgetData.badge(2.5));  // metade para cima, como o site
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

    @Test public void brandLogoOnlyWhenNameFits() {  // 1.8: marca comprida no topo; nome de grupo longo volta ao logo quadrado
        assertTrue(WidgetData.longLogo("Favoritos", 323, 90, 1f, true));                        // print do Jefferson (≈323dp)
        assertFalse(WidgetData.longLogo("Pequenas e médias promissoras", 323, 90, 1f, true));
        assertFalse(WidgetData.longLogo("Favoritos", 250, 90, 1f, true));                       // widget estreito
        assertTrue(WidgetData.longLogo("Pequenas e médias promissoras", 520, 90, 1f, true));    // largo (paisagem)
        assertFalse(WidgetData.longLogo("Favoritos", 323, 90, 1.6f, true));                     // fonte grande do aparelho
        assertTrue(WidgetData.longLogo("Dividendos", 323, 90, 1f, false));
        assertFalse(WidgetData.longLogo("Favoritos", 0, 90, 1f, true));                         // largura desconhecida: quadrado
        assertTrue(WidgetData.brandRoom("Favoritos", 323, 1f, true) > 90);                      // sobra para esticar a marca
        assertEquals(190, WidgetData.brandGrafPx(100, 200, 190, 600));                          // nunca menor que a compacta
        assertEquals(500, WidgetData.brandGrafPx(700, 200, 190, 600));                          // estica até o seletor
        assertEquals(900, WidgetData.brandGrafPx(2000, 200, 190, 600));                         // no máximo 1,5× a natural
        assertEquals(300, WidgetData.widthDp(300, 560, false));
        assertEquals(560, WidgetData.widthDp(300, 560, true));
        assertEquals(560, WidgetData.widthDp(0, 560, false));
    }

    // ---------- 1.10: troca rápida de grupo (A→B→A), respostas fora de ordem e logos lentos ----------
    private static String resp(String... tl) {  // {"r":[{"t":..,"p":..,"l":..}]} ; tl = ticker, preço, arquivo do logo
        StringBuilder b = new StringBuilder("{\"r\":[");
        for (int i = 0; i < tl.length; i += 3)
            b.append(i > 0 ? "," : "").append("{\"t\":\"").append(tl[i]).append("\",\"p\":").append(tl[i + 1]).append(",\"l\":\"").append(tl[i + 2]).append("\"}");
        return b.append("]}").toString();
    }

    /** Guarda como o Store: por lista, só a resposta pedida por último (WidgetData.accept). */
    private static final class FakeStore {
        final java.util.Map<String, String> data = new java.util.HashMap<>();
        final java.util.Map<String, Long> req = new java.util.HashMap<>();
        void offer(String sel, long r, String json) {
            if (WidgetData.accept(r, req.getOrDefault(sel, Long.MIN_VALUE))) { data.put(sel, json); req.put(sel, r); }
        }
    }

    @Test public void quickSwitchOutOfOrderKeepsNewestAndOwnLogos() {
        java.util.List<String> a = Arrays.asList("PETR4", "VALE3"), b = Arrays.asList("ITUB4", "BBAS3");
        String a1 = resp("PETR4", "30", "aaaaaaaaaaa1.png", "VALE3", "60", "aaaaaaaaaaa2.png");   // A pedido em t=1 (lento)
        String bb = resp("ITUB4", "35", "bbbbbbbbbbb1.png", "BBAS3", "23", "bbbbbbbbbbb2.png");   // B em t=2
        String a3 = resp("PETR4", "31", "aaaaaaaaaaa1.png", "VALE3", "61", "aaaaaaaaaaa2.png");   // A de novo em t=3
        FakeStore st = new FakeStore();
        st.offer("A", 3, a3); st.offer("B", 2, bb); st.offer("A", 1, a1);  // chegam ao contrário
        assertEquals(a3, st.data.get("A"));                                 // a antiga não apaga a nova
        java.util.List<WidgetData.Item> ia = WidgetData.items(a, st.data.get("A")), ib = WidgetData.items(b, st.data.get("B"));
        assertEquals(31.0, ia.get(0).p, 1e-9);
        java.util.Set<String> all = new java.util.HashSet<>(Arrays.asList("aaaaaaaaaaa1.png", "aaaaaaaaaaa2.png", "bbbbbbbbbbb1.png", "bbbbbbbbbbb2.png"));
        assertEquals("aaaaaaaaaaa1.png", WidgetData.logoFile(ia.get(0), all::contains));  // logo da própria ação
        assertEquals("bbbbbbbbbbb2.png", WidgetData.logoFile(ib.get(1), all::contains));
        // logos lentos: o de B ainda não baixou -> iniciais (null), nunca o logo que estava na mesma posição em A
        java.util.Set<String> onlyA = new java.util.HashSet<>(Arrays.asList("aaaaaaaaaaa1.png", "aaaaaaaaaaa2.png"));
        for (WidgetData.Item it : ib) assertNull(WidgetData.logoFile(it, onlyA::contains));
        // grupo trocado antes da resposta: lista nova sem dado -> só tickers, sem logo
        for (WidgetData.Item it : WidgetData.items(b, "{}")) assertNull(WidgetData.logoFile(it, all::contains));
        // resposta de B sem uma ação (lista mudou): a linha que falta não herda logo de ninguém
        java.util.List<WidgetData.Item> ic = WidgetData.items(Arrays.asList("ITUB4", "WEGE3"), bb);
        assertNull(WidgetData.logoFile(ic.get(1), all::contains));
    }

    // 1.22: celular reiniciou — o número do pedido é um contador guardado (Store.nextReq), não o System.nanoTime (que volta a zero);
    // com nanoTime, depois do reinício toda resposta parecia mais antiga que a guardada e o widget ficava parado
    @Test public void phoneRebootDoesNotFreezeWidget() {
        long antesNano = 9_000_000_000_000L, depoisNano = 5_000_000L;      // nanoTime antes e depois do reinício
        assertFalse(WidgetData.accept(depoisNano, antesNano));             // o defeito da 1.21: resposta nova descartada
        FakeStore st = new FakeStore(); long seq = 0;                       // 1.22: chave nova (dseq_), contador que só sobe
        st.offer("A", ++seq, "antes"); /* reinício: o contador continua de onde parou */ st.offer("A", ++seq, "depois");
        assertEquals("depois", st.data.get("A"));
        assertTrue(WidgetData.accept(1, Long.MIN_VALUE));                   // quem estava preso: 1ª resposta na chave nova é aceita
    }

    @Test public void loadingClearedOnlyByLatestRefresh() {  // ⟳ / troca A→B→A: a primeira busca a terminar não apaga o "Atualizando…" da última
        assertFalse(WidgetData.ownsLoading(100, 200));
        assertTrue(WidgetData.ownsLoading(200, 200));
        assertTrue(WidgetData.accept(5, 5)); assertFalse(WidgetData.accept(4, 5));
    }

    @Test public void popularNameFits() {  // 1.11: nome em cima, maior tamanho que cabe; nome longo vai para 2 linhas em 12 sp
        float room = WidgetData.nameRoomDp(363, false);   // largura do print do Jefferson
        assertEquals(14f, WidgetData.nameSp("Petrobras", room), 1e-6);
        assertTrue(WidgetData.nameSp("Caixa Seguridade", room) < 14f);
        assertEquals(12f, WidgetData.nameSp("BB Seguridade", 90f), 1e-6);  // 1.21: mais de uma palavra que não cabe → 2 linhas
        assertEquals(12f, WidgetData.nameSp("Jerónimo Martins Investimentos", room), 1e-6);
        assertTrue(WidgetData.nameRoomDp(250, true) >= 40);
    }

    @Test public void wholeRowsFillHeight() {  // 1.12: N linhas inteiras e a última rente à borda
        float d = 2.75f;
        int base = Math.round(46 * d), div = 3;
        for (int hDp : new int[]{180, 250, 300, 333, 420, 500, 640}) {
            int list = Math.round((hDp - WidgetData.headerDp(1f, false)) * d);
            int[] r = WidgetData.rows(list, d, 1f, 40);
            assertTrue(r[0] >= 1);
            assertTrue(r[1] >= base);                                  // nunca menor que a base
            int used = r[0] * r[1] + (r[0] - 1) * div;
            if (r[1] < Math.round(base * 1.6f)) assertTrue(list - used >= 0 && list - used < r[0]);  // sobra < 1 px por linha
            assertTrue((r[0] + 1) * base + r[0] * div > list);       // não caberia mais uma linha base
        }
        int list = Math.round((500 - WidgetData.headerDp(1f, false)) * d);
        assertEquals(base, WidgetData.rows(list, d, 1f, 3)[1]);       // poucos itens: base, espaço vazio embaixo
        assertEquals(1, WidgetData.rows(50, d, 1f, 10)[0]);            // lista mais baixa que uma linha
        assertEquals(base, WidgetData.rows(50, d, 1f, 10)[1]);
        assertTrue(WidgetData.rows(list, d, 1.3f, 40)[0] < WidgetData.rows(list, d, 1f, 40)[0]);  // fonte grande: menos linhas
        assertEquals(500, WidgetData.heightDp(300, 500, false));
        assertEquals(300, WidgetData.heightDp(300, 500, true));
    }

    @Test public void showsFetchTimeAndRefreshState() {  // 1.13: horário = fim da busca; estado do servidor
        java.util.TimeZone sp = java.util.TimeZone.getTimeZone("America/Sao_Paulo");
        long t = 1792357259000L;  // 2026-10-18 21:00:59 UTC = 18:00:59 em Brasília
        assertEquals("18/10 18:00", WidgetData.fetched(t, sp));
        assertEquals("18/10 18:01", WidgetData.fetched(t + 2000, sp));  // terminou no minuto seguinte: mostra o do fim
        assertTrue(WidgetData.refreshing("{\"started\":true,\"refreshing\":true}"));
        assertFalse(WidgetData.refreshing("{\"started\":false,\"refreshing\":false}"));
        assertFalse(WidgetData.refreshing(null));
        assertFalse(WidgetData.refreshing("<html>"));
    }

    // 1.21: coluna Ação do tamanho do maior nome; nome de 2+ palavras que não cabe em 14 sp vai para 2 linhas a 12 sp
    @Test public void colunaAcaoPeloMaiorNome() {
        WidgetData.Meas m = (s, sp, bold) -> s.length() * 0.55f * sp;
        java.util.List<String> nm = java.util.Arrays.asList("Petrobras", "BB Seguridade", "Caixa Seguridade", "Klabin"),
                tk = java.util.Arrays.asList("PETR3", "BBSE3", "CXSE3", "KLBN3");
        WidgetData.Cols c = WidgetData.cols(nm, tk, 200f, m);
        float seg = 10 * 0.55f * 12f;  // "Seguridade" a 12 sp
        assertEquals(Math.max(9 * 0.55f * 14f, seg), c.text - 2, 1.01f);  // o maior: "Petrobras" a 14 sp
        assertEquals(14f, c.sp[0], 1e-6); assertEquals(12f, c.sp[1], 1e-6); assertEquals(12f, c.sp[2], 1e-6); assertEquals(14f, c.sp[3], 1e-6);
        assertEquals(200f - c.text, c.extra, 1e-3);  // a sobra vai para as outras colunas
        WidgetData.Cols c2 = WidgetData.cols(java.util.Arrays.asList("Klabin"), java.util.Arrays.asList("KLBN3"), 200f, m);
        assertTrue(c2.text < c.text && c2.extra > c.extra);  // muda com as empresas
        assertEquals(40f, WidgetData.cols(nm, tk, 40f, m).text, 1e-6);  // nunca mais que o espaço
        int[] h = WidgetData.heightVariants(400);
        assertEquals(416, h[0]); assertEquals(352, h[h.length - 1]);
    }
}
