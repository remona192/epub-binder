package com.simplefiles.core

import org.apache.commons.compress.archivers.sevenz.SevenZOutputFile
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Rule
import org.junit.Test
import org.junit.rules.TemporaryFolder
import java.io.File
import java.nio.charset.Charset
import java.util.zip.ZipEntry
import java.util.zip.ZipOutputStream

class ArchiveReaderTest {
    @get:Rule val tmp = TemporaryFolder()

    private fun zip(file: File, charset: Charset, entries: Map<String, String>) {
        ZipOutputStream(file.outputStream(), charset).use { z ->
            entries.forEach { (n, c) ->
                z.putNextEntry(ZipEntry(n))
                z.write(c.toByteArray())
                z.closeEntry()
            }
        }
    }

    @Test fun listsUtf8ZipWithSynthesizedFolders() {
        val f = tmp.newFile("books.zip")
        zip(f, Charsets.UTF_8, mapOf("소설/내가 잘못했다면 1권.txt" to "a", "readme.md" to "b"))
        val items = ArchiveReader.list(f)
        val paths = items.map { it.path }.toSet()
        assertEquals(setOf("소설/내가 잘못했다면 1권.txt", "readme.md", "소설"), paths)
        assertTrue(items.first { it.path == "소설" }.isDirectory)
        assertEquals("내가 잘못했다면 1권.txt", items.first { it.path.endsWith(".txt") }.name)
    }

    @Test fun decodesCp949ZipNames() {
        val f = tmp.newFile("win.zip")
        zip(f, Charset.forName("MS949"), mapOf("한글 파일.txt" to "x"))
        assertEquals(listOf("한글 파일.txt"), ArchiveReader.list(f).map { it.path })
        val out = File(tmp.root, "out/한글 파일.txt")
        assertTrue(ArchiveReader.extract(f, "한글 파일.txt", out))
        assertEquals("x", out.readText())
    }

    @Test fun listsAndExtracts7z() {
        val f = File(tmp.root, "pack.7z")
        SevenZOutputFile(f).use { z ->
            val src = tmp.newFile("src.txt").apply { writeText("seven") }
            val e = z.createArchiveEntry(src, "폴더/내가 잘못했다면.txt")
            z.putArchiveEntry(e)
            z.write(src.readBytes())
            z.closeArchiveEntry()
        }
        val items = ArchiveReader.list(f)
        assertTrue(items.any { it.path == "폴더/내가 잘못했다면.txt" && !it.isDirectory })
        val out = File(tmp.root, "x.txt")
        assertTrue(ArchiveReader.extract(f, "폴더/내가 잘못했다면.txt", out))
        assertEquals("seven", out.readText())
    }

    @Test fun brokenArchiveIsEmpty() {
        val f = tmp.newFile("bad.zip").apply { writeText("not a zip") }
        assertTrue(ArchiveReader.list(f).isEmpty())
    }
}
