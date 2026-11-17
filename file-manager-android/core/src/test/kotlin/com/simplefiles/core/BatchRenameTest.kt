package com.simplefiles.core

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Rule
import org.junit.Test
import org.junit.rules.TemporaryFolder
import java.io.File

class BatchRenameTest {
    @get:Rule val tmp = TemporaryFolder()

    private fun inputs(vararg names: String) = names.map { RenameInput("/d/$it", it, false) }
    private fun names(plan: RenamePlan) = plan.previews.map { it.newName }
    private val none: (File) -> Boolean = { false }

    @Test fun regexReplaceWithGroups() {
        val p = BatchRenamer.plan(
            inputs("[작가] 제목 01권.epub", "[작가] 제목 02권.epub"),
            listOf(RenameRule.Replace("^\\[(.+?)\\]\\s*(.+)$", "$2 - $1", regex = true)),
            includeExtension = false, exists = none,
        )
        assertEquals(listOf("제목 01권 - 작가.epub", "제목 02권 - 작가.epub"), names(p))
    }

    @Test fun literalReplaceTreatsSymbolsLiterally() {
        val p = BatchRenamer.plan(inputs("a.b(1).txt"), listOf(RenameRule.Replace("(1)", "$")), false, none)
        assertEquals("a.b$.txt", names(p)[0])
    }

    @Test fun invalidRegexReported() {
        val p = BatchRenamer.plan(inputs("a.txt"), listOf(RenameRule.Replace("([", "", regex = true)), false, none)
        assertNotNull(p.ruleError)
        assertTrue(p.hasErrors)
    }

    @Test fun numberingInsertRemoveCaseExt() {
        val rules = listOf(
            RenameRule.Remove(start = 0, count = 2),
            RenameRule.Insert("새_", TextPosition.START),
            RenameRule.Numbering(start = 1, digits = 3, position = TextPosition.END, separator = "-"),
            RenameRule.ChangeCase(CaseMode.UPPER),
            RenameRule.Extension("md"),
        )
        val p = BatchRenamer.plan(inputs("xxabc.txt", "xxdef.txt"), rules, false, none)
        assertEquals(listOf("새_ABC-001.md", "새_DEF-002.md"), names(p))
    }

    @Test fun removeFromEnd() {
        val p = BatchRenamer.plan(inputs("title_old.txt"), listOf(RenameRule.Remove(0, 4, fromEnd = true)), false, none)
        assertEquals("title.txt", names(p)[0])
    }

    @Test fun templateTokens() {
        val ins = listOf(RenameInput("/books/소설/a.epub", "a.epub", false))
        val p = BatchRenamer.plan(ins, listOf(RenameRule.Template("{parent}_{n:3}_{name}")), false, none)
        assertEquals("소설_001_a.epub", names(p)[0])
    }

    @Test fun duplicateResultsAreErrors() {
        val p = BatchRenamer.plan(inputs("a1.txt", "a2.txt"), listOf(RenameRule.Replace("\\d", "", regex = true)), false, none)
        assertTrue(p.previews.all { it.error != null })
    }

    @Test fun existingFileIsError() {
        val p = BatchRenamer.plan(inputs("a.txt"), listOf(RenameRule.Insert("b")), false, exists = { it.name == "ba.txt" })
        assertNotNull(p.previews[0].error)
    }

    @Test fun includeExtensionMode() {
        val p = BatchRenamer.plan(inputs("a.txt"), listOf(RenameRule.Replace(".txt", ".md")), true, none)
        assertEquals("a.md", names(p)[0])
    }

    @Test fun executeSwapAndUndo() {
        val d = tmp.root
        File(d, "a.txt").writeText("A")
        File(d, "b.txt").writeText("B")
        val res = BatchRenamer.execute(listOf(File(d, "a.txt") to "b.txt", File(d, "b.txt") to "a.txt"))
        assertTrue(res.failures.isEmpty())
        assertEquals("B", File(d, "a.txt").readText())
        assertEquals("A", File(d, "b.txt").readText())
        BatchRenamer.undo(res.applied)
        assertEquals("A", File(d, "a.txt").readText())
    }

    @Test fun swapWithinSelectionIsNotConflict() {
        val d = tmp.root
        File(d, "a.txt").writeText("A")
        File(d, "b.txt").writeText("B")
        val ins = listOf(RenameInput(File(d, "a.txt").path, "a.txt", false), RenameInput(File(d, "b.txt").path, "b.txt", false))
        val p = BatchRenamer.plan(
            ins,
            listOf(RenameRule.Replace("^(a|b)$", "x", regex = true), RenameRule.Template("{name}")),
            false,
        )
        // 둘 다 x.txt가 되므로 중복 오류
        assertTrue(p.previews.all { it.error != null })
        val p2 = BatchRenamer.plan(ins, listOf(RenameRule.Template("{n}")), false)
        assertNull(p2.previews[0].error)
    }
}

class BatchRenameBinderOptionsTest {
    private fun inputs(vararg names: String) = names.map { RenameInput("/d/$it", it, false) }
    private val none: (java.io.File) -> Boolean = { false }

    @Test fun overwriteAndEpisodeSuffix() {
        val p = BatchRenamer.plan(
            inputs("a 3화.txt", "b.txt"),
            listOf(RenameRule.Overwrite("[작가] 제목"), RenameRule.EpisodeSuffix(start = 1, unit = "화")),
            false, none,
        )
        assertEquals(listOf("[작가] 제목 1화.txt", "[작가] 제목 2화.txt"), p.previews.map { it.newName })
    }

    @Test fun scopeOnlyIncludedAndNumbersCountIncludedOnly() {
        val ins = inputs("a.txt", "b.txt", "c.txt")
        val p = BatchRenamer.plan(
            ins, listOf(RenameRule.EpisodeSuffix(unit = "권")), false, none,
            included = setOf("/d/a.txt", "/d/c.txt"),
        )
        assertEquals(listOf("a 1권.txt", "b.txt", "c 2권.txt"), p.previews.map { it.newName })
        assertTrue(p.previews[1].excluded)
        assertEquals(2, p.changes.size)
    }

    @Test fun postOptions() {
        val name = java.text.Normalizer.normalize("[작가]_제목_()_12회차.txt", java.text.Normalizer.Form.NFD)
        val p = BatchRenamer.plan(
            inputs(name), emptyList(), false, none,
            post = RenamePostOptions(cleanup = true, unifyEpisode = true, fixJamo = true, underscoreToSpace = true),
        )
        assertEquals("[작가] 제목 12화.txt", p.previews[0].newName)
    }
}
