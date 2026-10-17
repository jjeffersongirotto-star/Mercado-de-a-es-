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

    @Test public void checkInterval() {
        long now = 1_800_000_000_000L;
        assertTrue(UpdateLogic.shouldCheck(0, now));
        assertFalse(UpdateLogic.shouldCheck(now - 3600_000L, now));
        assertTrue(UpdateLogic.shouldCheck(now - UpdateLogic.CHECK_EVERY, now));
        assertTrue(UpdateLogic.shouldCheck(now + 60_000L, now));   // relógio voltou
        assertEquals("00ff10", UpdateLogic.hex(new byte[]{0, (byte) 0xff, 0x10}));
    }
}
