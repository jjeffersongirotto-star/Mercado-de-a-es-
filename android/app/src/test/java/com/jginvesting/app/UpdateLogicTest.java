package com.jginvesting.app;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertFalse;
import static org.junit.Assert.assertNotEquals;
import static org.junit.Assert.assertNotNull;
import static org.junit.Assert.assertNull;
import static org.junit.Assert.assertTrue;

import org.junit.Test;

public class UpdateLogicTest {
    static final String SHA = "6c565674bdf9530716f5ae640623a5ec3b4d7d1252ccc92ffdb40e1f91c170e8";
    static String json(int code) { return "{\"versionCode\":" + code + ",\"versionName\":\"1." + (code - 1) + "\",\"apk\":\"/app.apk\",\"sha256\":\"" + SHA.toUpperCase() + "\"}"; }

    @Test public void parse() {
        UpdateLogic.Info i = UpdateLogic.parse(json(4));
        assertNotNull(i); assertEquals(4, i.code); assertEquals("1.3", i.name); assertEquals("/app.apk", i.apk); assertEquals(SHA, i.sha256);
        assertNull(UpdateLogic.parse("{}"));
        assertNull(UpdateLogic.parse("{\"versionCode\":4,\"versionName\":\"1.3\",\"apk\":\"/app.apk\",\"sha256\":\"xyz\"}"));
        assertNull(UpdateLogic.parse("{\"versionCode\":4,\"versionName\":\"1.3\",\"apk\":\"https://outro.site/x.apk\",\"sha256\":\"" + SHA + "\"}"));
        assertNull(UpdateLogic.parse("lixo"));
    }

    @Test public void offerOnlyNewerAndNotSnoozed() {
        long now = 1_800_000_000_000L;
        UpdateLogic.Info i = UpdateLogic.parse(json(4));
        assertTrue(UpdateLogic.offer(i, 3, 0, 0, now));
        assertFalse(UpdateLogic.offer(i, 4, 0, 0, now));          // mesma versão
        assertFalse(UpdateLogic.offer(i, 5, 0, 0, now));          // instalada mais nova
        assertFalse(UpdateLogic.offer(null, 3, 0, 0, now));
        long until = now + UpdateLogic.SNOOZE;                     // "Depois" na versão 4
        assertFalse(UpdateLogic.offer(i, 3, 4, until, now + 60_000L));
        assertTrue(UpdateLogic.offer(i, 3, 4, until, until));      // passou o prazo do "Depois"
        assertTrue(UpdateLogic.offer(UpdateLogic.parse(json(5)), 3, 4, until, now));  // versão mais nova: oferece de novo
    }

    /** Caso real (17/10/2026): 1.2 aberta na instalação (~00:07, site ainda na 1.2), 1.3 publicada às 00:34, app aberto às 00:40. */
    @Test public void rootCauseThreeHourThrottle() {
        long install = 1_791_947_220_000L, open = install + 33 * 60_000L;   // 00:07 e 00:40 (horário de Brasília)
        long legacy = 3 * 3600_000L;                                       // regra da 1.2
        assertFalse(UpdateLogic.shouldCheck(install, open, legacy));       // 1.2: não confere -> sem oferta (o bug)
        assertTrue(UpdateLogic.shouldCheck(install, install + legacy, legacy));  // 1.2: só a partir de ~03:07
        assertTrue(UpdateLogic.shouldCheck(install, open));                // 1.4: confere e oferece
        assertTrue(UpdateLogic.offer(UpdateLogic.parse(json(4)), 3, 0, 0, open));
    }

    @Test public void failureDoesNotCount() {
        long now = 1_800_000_000_000L, last = now - UpdateLogic.CHECK_EVERY;
        long after = UpdateLogic.afterCheck(last, null, now);              // servidor acordando / sem rede
        assertEquals(last, after);
        assertTrue(UpdateLogic.shouldCheck(after, now + 1000));           // próxima abertura tenta de novo
        long ok = UpdateLogic.afterCheck(last, UpdateLogic.parse(json(4)), now);
        assertEquals(now, ok);
        assertFalse(UpdateLogic.shouldCheck(ok, now + 60_000L));
        assertTrue(UpdateLogic.RETRY_MS.length >= 3);
    }

    /** O version.json publicado (o mesmo arquivo servido em /app/version.json) é aceito pela regra da 1.2 e da 1.4. */
    @Test public void publishedVersionJsonIsOffered() throws Exception {
        String j = new String(java.nio.file.Files.readAllBytes(java.nio.file.Paths.get("../../static/app/version.json")), "UTF-8");
        UpdateLogic.Info i = UpdateLogic.parse(j);
        assertNotNull(i);
        assertEquals("/app.apk", i.apk);
        assertTrue(i.code >= 4);
        assertTrue(UpdateLogic.offer(i, 3, 0, 0, 0));   // 1.2 instalada
        assertTrue(UpdateLogic.available(i, i.code - 1)); // versão anterior instalada
        assertFalse(UpdateLogic.available(i, i.code));
    }

    /** Nomes de versão comparados por número (nunca como texto: "1.10" < "1.9" seria o erro). */
    @Test public void versionNameNumeric() {
        assertTrue(UpdateLogic.cmpName("1.10", "1.9") > 0);
        assertTrue(UpdateLogic.cmpName("1.13", "1.9") > 0);
        assertTrue(UpdateLogic.cmpName("1.14", "1.13") > 0);
        assertTrue(UpdateLogic.cmpName("1.9", "1.10") < 0);
        assertTrue(UpdateLogic.cmpName("2.0", "1.99") > 0);
        assertEquals(0, UpdateLogic.cmpName("1.13", "1.13"));
        assertEquals(0, UpdateLogic.cmpName("1.13", "1.13.0"));
        assertTrue(UpdateLogic.cmpName("1.13.1", "1.13") > 0);
        assertTrue(UpdateLogic.cmpName("1.14-beta", "1.13") > 0);
        assertEquals(0, UpdateLogic.cmpName(null, ""));
        assertTrue("1.10".compareTo("1.9") < 0);  // a comparação de texto erraria
    }

    @Test public void newerUsesCodeThenName() {
        UpdateLogic.Info i = UpdateLogic.parse("{\"versionCode\":15,\"versionName\":\"1.14\",\"apk\":\"/app.apk\",\"sha256\":\"" + SHA + "\"}");
        assertTrue(UpdateLogic.newer(i, 14, "1.13"));
        assertTrue(UpdateLogic.newer(i, 11, "1.10"));
        assertFalse(UpdateLogic.newer(i, 15, "1.14"));
        assertFalse(UpdateLogic.newer(i, 16, "1.15"));
        assertTrue(UpdateLogic.newer(i, 15, "1.13"));   // mesmo código, nome maior (código esquecido): oferece
        assertFalse(UpdateLogic.newer(i, 15, "1.20"));
        assertFalse(UpdateLogic.newer(null, 1, "1.0"));
        assertTrue(UpdateLogic.available(i, 14, "1.13") && UpdateLogic.offer(i, 14, "1.13", 0, 0, 0));
    }

    /** Caso real (17/10/2026): 1.12 em uso e widget conferindo (30 min e cada ⟳) enquanto a 1.13 era publicada; app aberto logo depois. */
    @Test public void rootCauseTenMinuteThrottleAndSnooze() {
        long widget = 1_792_000_000_000L, open = widget + 4 * 60_000L;  // widget conferiu (site ainda na versão antiga); app aberto 4 min depois
        assertFalse(UpdateLogic.shouldCheck(widget, open));             // 1.13: trava de 10 min (contava a conferência do widget) -> sem oferta
        assertTrue(UpdateLogic.openCheck(0, open));                    // 1.14: abrir (processo novo) sempre confere
        assertTrue(UpdateLogic.openCheck(open, open + UpdateLogic.OPEN_GAP));  // voltar ao app também
        assertFalse(UpdateLogic.openCheck(open, open + 2_000L));       // só junta aberturas seguidas
        assertTrue(UpdateLogic.openCheck(open, open - 1));             // relógio voltou
        assertTrue(UpdateLogic.SNOOZE <= 10 * 60_000L);                // "Depois" não segura mais um dia inteiro
    }

    @Test public void urlWithoutCache() {
        assertEquals("https://x/app/version.json?t=5", UpdateLogic.url("https://x", 5));
        assertTrue(!UpdateLogic.url("https://x", 5).equals(UpdateLogic.url("https://x", 6)));
    }

    @Test public void checkInterval() {
        long now = 1_800_000_000_000L;
        assertTrue(UpdateLogic.shouldCheck(0, now));
        assertFalse(UpdateLogic.shouldCheck(now - 60_000L, now));
        assertTrue(UpdateLogic.shouldCheck(now - UpdateLogic.CHECK_EVERY, now));
        assertTrue(UpdateLogic.shouldCheck(now + 60_000L, now));   // relógio voltou
        assertEquals("00ff10", UpdateLogic.hex(new byte[]{0, (byte) 0xff, 0x10}));
    }

    @Test public void conferenciaAcompanhaCadaAtualizacaoDeDados() {
        // 1.15: cada atualização de dados (widget, ⟳, recarga do site) confere a versão; só junta as que vêm em menos de OPEN_GAP
        long t = 1_000_000L;
        assertTrue(UpdateLogic.dataCheck(0, t));
        assertFalse(UpdateLogic.dataCheck(t, t + 5_000));
        assertTrue(UpdateLogic.dataCheck(t, t + UpdateLogic.OPEN_GAP));
        assertTrue(UpdateLogic.dataCheck(t, t + 30 * 60_000L));  // widget a cada 30 min: sem a trava antiga de 10 min contando o widget
        assertTrue(UpdateLogic.dataCheck(t, t - 1));            // relógio voltou
        // endereço muda a cada conferência (sem cache em CDN/proxy/WebView)
        assertNotEquals(UpdateLogic.url("https://x", t), UpdateLogic.url("https://x", t + 1));
        // "Depois" = 10 min só para a versão adiada; versão mais nova aparece mesmo adiada
        UpdateLogic.Info v16 = UpdateLogic.parse("{\"versionCode\":16,\"versionName\":\"1.15\",\"apk\":\"/app.apk\",\"sha256\":\"" + "a".repeat(64) + "\"}");
        UpdateLogic.Info v17 = UpdateLogic.parse("{\"versionCode\":17,\"versionName\":\"1.16\",\"apk\":\"/app.apk\",\"sha256\":\"" + "a".repeat(64) + "\"}");
        assertFalse(UpdateLogic.offer(v16, 15, "1.14", 16, t + UpdateLogic.SNOOZE, t + 60_000));
        assertTrue(UpdateLogic.offer(v16, 15, "1.14", 16, t + UpdateLogic.SNOOZE, t + UpdateLogic.SNOOZE));
        assertTrue(UpdateLogic.offer(v17, 15, "1.14", 16, t + UpdateLogic.SNOOZE, t + 60_000));
        assertEquals(10 * 60_000L, UpdateLogic.SNOOZE);
    }
}
