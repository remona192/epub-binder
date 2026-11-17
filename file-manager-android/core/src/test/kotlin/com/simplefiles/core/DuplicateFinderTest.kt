package com.simplefiles.core

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class DuplicateFinderTest {
    private fun c(name: String, t: Long = 0) = DupCandidate("/s/$name", name, 10, t)
    private fun groupNames(gs: List<DupGroup>) = gs.map { g -> g.members.map { it.file.name }.toSet() }.toSet()

    @Test fun ninetyPercentGroups() {
        val files = listOf(
            c("내가 잘못했다면 완결판.epub"),
            c("내가 잘못했다면  완결판.epub"),
            c("내가_잘못했다면_완결판.epub"),
            c("내가 잘못했다면 완결편.epub"), // 1글자 차이 (11자 중) -> 90.9%
            c("전혀 다른 책.epub"),
        )
        val g = DuplicateFinder.find(files)
        assertEquals(1, g.size)
        assertEquals(4, g[0].members.size)
    }

    @Test fun belowThresholdNotGrouped() {
        val g = DuplicateFinder.find(listOf(c("abcdefghij.txt"), c("abcdefgxyz.txt")))
        assertTrue(g.isEmpty())
    }

    @Test fun differentVolumesExcludedByDefault() {
        val files = listOf(c("아주 긴 소설 제목 1권.epub"), c("아주 긴 소설 제목 2권.epub"))
        assertTrue(DuplicateFinder.find(files).isEmpty())
        assertEquals(1, DuplicateFinder.find(files, DupOptions(excludeDifferentNumbers = false)).size)
    }

    @Test fun sameExtensionOption() {
        val files = listOf(c("report final.pdf"), c("report final.docx"))
        assertTrue(DuplicateFinder.find(files).isEmpty())
        assertEquals(1, DuplicateFinder.find(files, DupOptions(sameExtension = false)).size)
    }

    @Test fun copyMarkersOption() {
        val files = listOf(c("사진.jpg"), c("사진 (1).jpg"), c("사진 - 복사본.jpg"))
        assertTrue(DuplicateFinder.find(files).isEmpty())
        val g = DuplicateFinder.find(files, DupOptions(ignoreCopyMarkers = true))
        assertEquals(setOf(setOf("사진.jpg", "사진 (1).jpg", "사진 - 복사본.jpg")), groupNames(g))
    }

    @Test fun transitiveGrouping() {
        // a~b, b~c 이면 a,b,c 한 그룹
        val g = DuplicateFinder.find(
            listOf(c("abcdefghijk.txt"), c("abcdefghijX.txt"), c("abcdefghiYX.txt")),
            DupOptions(threshold = 0.9),
        )
        assertEquals(1, g.size)
        assertEquals(3, g[0].members.size)
    }

    @Test fun levenshteinBasics() {
        assertEquals(3, DuplicateFinder.levenshtein("kitten", "sitting", 10))
        assertEquals(2, DuplicateFinder.levenshtein("kitten", "sitting", 1))
        assertTrue(DuplicateFinder.similarity("abc", "abc") == 1.0)
        assertFalse(DuplicateFinder.isSimilar("abcd", "abce", DupOptions(threshold = 0.9)))
    }
}
