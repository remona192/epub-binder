package com.simplefiles.core

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Rule
import org.junit.Test
import org.junit.rules.TemporaryFolder

class NameUtilTest {
    @get:Rule val tmp = TemporaryFolder()

    @Test fun splitExt() {
        assertEquals("a.tar" to "gz", NameUtil.splitExt("a.tar.gz"))
        assertEquals(".nomedia" to "", NameUtil.splitExt(".nomedia"))
        assertEquals("noext" to "", NameUtil.splitExt("noext"))
        assertEquals("dot." to "", NameUtil.splitExt("dot."))
    }

    @Test fun uniqueName() {
        val d = tmp.root
        assertEquals("a.txt", NameUtil.uniqueName(d, "a.txt", false))
        d.resolve("a.txt").writeText("x")
        assertEquals("a (1).txt", NameUtil.uniqueName(d, "a.txt", false))
        d.resolve("a (1).txt").writeText("x")
        assertEquals("a (2).txt", NameUtil.uniqueName(d, "a.txt", false))
        d.resolve("f.v").mkdir()
        assertEquals("f.v (1)", NameUtil.uniqueName(d, "f.v", true))
    }

    @Test fun invalid() {
        assertNotNull(NameUtil.invalidReason(""))
        assertNotNull(NameUtil.invalidReason("a/b"))
        assertNull(NameUtil.invalidReason("내가 잘못했다면.txt"))
    }
}
