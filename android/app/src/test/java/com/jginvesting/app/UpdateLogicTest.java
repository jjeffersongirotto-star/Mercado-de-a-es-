package com.jginvesting.app;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertFalse;
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
        assertFalse(UpdateLogic.offer(i, 3, 4, until, now + 3600_000L));
        assertTrue(UpdateLogic.offer(i, 3, 4, until, until));      // passou um dia
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

    @Test public void checkInterval() {
        long now = 1_800_000_000_000L;
        assertTrue(UpdateLogic.shouldCheck(0, now));
        assertFalse(UpdateLogic.shouldCheck(now - 60_000L, now));
        assertTrue(UpdateLogic.shouldCheck(now - UpdateLogic.CHECK_EVERY, now));
        assertTrue(UpdateLogic.shouldCheck(now + 60_000L, now));   // relógio voltou
        assertEquals("00ff10", UpdateLogic.hex(new byte[]{0, (byte) 0xff, 0x10}));
    }
}
