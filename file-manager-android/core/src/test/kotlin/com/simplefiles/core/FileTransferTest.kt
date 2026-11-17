package com.simplefiles.core

import kotlinx.coroutines.test.runTest
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Rule
import org.junit.Test
import org.junit.rules.TemporaryFolder
import java.io.File

class FileTransferTest {
    @get:Rule val tmp = TemporaryFolder()

    private fun transfer(choice: ConflictChoice = ConflictChoice.SKIP, all: Boolean = true, asked: MutableList<String>? = null) =
        FileTransfer(onConflict = { s, _ -> asked?.add(s.name); ConflictDecision(choice, all) })

    private fun file(dir: File, name: String, text: String) = File(dir, name).apply { parentFile.mkdirs(); writeText(text) }

    @Test fun copyIntoSameFolderMakesNumberedCopy() = runTest {
        val d = tmp.newFolder("d")
        val a = file(d, "a.txt", "1")
        val r = transfer().run(listOf(a), d, TransferMode.COPY)
        assertEquals(1, r.succeeded)
        assertEquals("1", File(d, "a (1).txt").readText())
    }

    @Test fun moveIntoSameFolderIsNoop() = runTest {
        val d = tmp.newFolder("d")
        val a = file(d, "a.txt", "1")
        val r = transfer().run(listOf(a), d, TransferMode.MOVE)
        assertEquals(0, r.succeeded)
        assertTrue(a.exists())
    }

    @Test fun moveFolderIntoItselfFails() = runTest {
        val d = tmp.newFolder("d")
        val sub = File(d, "sub").apply { mkdirs() }
        val r = transfer().run(listOf(d), sub, TransferMode.MOVE)
        assertEquals(1, r.failures.size)
        assertTrue(d.exists())
    }

    @Test fun conflictSkipReplaceKeepBoth() = runTest {
        val src = tmp.newFolder("src")
        val dst = tmp.newFolder("dst")
        val a = file(src, "a.txt", "new")
        file(dst, "a.txt", "old")

        transfer(ConflictChoice.SKIP).run(listOf(a), dst, TransferMode.COPY)
        assertEquals("old", File(dst, "a.txt").readText())

        transfer(ConflictChoice.KEEP_BOTH).run(listOf(a), dst, TransferMode.COPY)
        assertEquals("new", File(dst, "a (1).txt").readText())

        transfer(ConflictChoice.REPLACE).run(listOf(a), dst, TransferMode.MOVE)
        assertEquals("new", File(dst, "a.txt").readText())
        assertFalse(a.exists())
    }

    @Test fun applyToAllAsksOnce() = runTest {
        val src = tmp.newFolder("src")
        val dst = tmp.newFolder("dst")
        val files = (1..3).map { file(src, "f$it.txt", "n$it") }
        (1..3).forEach { file(dst, "f$it.txt", "o$it") }
        val asked = mutableListOf<String>()
        transfer(ConflictChoice.REPLACE, all = true, asked = asked).run(files, dst, TransferMode.COPY)
        assertEquals(1, asked.size)
        assertEquals("n3", File(dst, "f3.txt").readText())
    }

    @Test fun replaceFolderMerges() = runTest {
        val src = tmp.newFolder("src")
        val dst = tmp.newFolder("dst")
        file(src, "box/a.txt", "a")
        file(dst, "box/b.txt", "b")
        val r = transfer(ConflictChoice.REPLACE).run(listOf(File(src, "box")), dst, TransferMode.MOVE)
        assertTrue(r.failures.isEmpty())
        assertEquals("a", File(dst, "box/a.txt").readText())
        assertEquals("b", File(dst, "box/b.txt").readText())
        assertFalse(File(src, "box").exists())
    }

    @Test fun copyFolderRecursively() = runTest {
        val src = tmp.newFolder("src")
        val dst = tmp.newFolder("dst")
        file(src, "box/x/y.txt", "y")
        File(src, "box/empty").mkdirs()
        val r = transfer().run(listOf(File(src, "box")), dst, TransferMode.COPY)
        assertEquals("y", File(dst, "box/x/y.txt").readText())
        assertTrue(File(dst, "box/empty").isDirectory)
        assertEquals(2, r.succeeded)
        assertTrue(File(src, "box/x/y.txt").exists())
    }
}
