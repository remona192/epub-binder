package com.simplefiles.core

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Rule
import org.junit.Test
import org.junit.rules.TemporaryFolder
import java.io.File

class TrashStoreTest {
    @get:Rule val tmp = TemporaryFolder()

    @Test fun trashRestoreAndPurge() {
        var clock = 1_000_000L
        val root = tmp.root
        val store = TrashStore(roots = { listOf(root) }, now = { clock })
        val f = File(root, "docs/a.txt").apply { parentFile.mkdirs(); writeText("hi") }

        assertTrue(store.moveToTrash(f))
        assertFalse(f.exists())
        val entries = store.list()
        assertEquals(1, entries.size)
        assertEquals("a.txt", entries[0].name)
        assertEquals(30, store.daysLeft(entries[0]))

        // 같은 이름이 생겼으면 (1)로 복원
        f.writeText("other")
        val restored = store.restore(entries[0])!!
        assertEquals("a (1).txt", restored.name)
        assertEquals("hi", restored.readText())
        assertTrue(store.list().isEmpty())

        store.moveToTrash(f)
        clock += 31L * 24 * 60 * 60 * 1000
        assertEquals(1, store.purgeExpired())
        assertTrue(store.list().isEmpty())
    }
}
