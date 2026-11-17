package com.simplefiles.core

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test
import java.io.File
import java.text.Normalizer

class NameFixerTest {
    private fun nfd(s: String) = Normalizer.normalize(s, Normalizer.Form.NFD)

    @Test fun jamo() {
        val split = nfd("내가 잘못했다면.txt")
        assertTrue(NameFixer.hasSplitJamo(split))
        assertEquals("내가 잘못했다면.txt", NameFixer.fixJamo(split))
    }

    @Test fun telegramUnderscore() {
        assertEquals("내가 잘못했다면 1-216.txt", NameFixer.fixTelegramUnderscore("내가_잘못했다면_1_216.txt"))
        assertEquals("내가 잘못했다면 1권.epub", NameFixer.fixTelegramUnderscore("내가_잘못했다면_1권.epub"))
        assertNull(NameFixer.fixTelegramUnderscore("IMG_20240101_1200.jpg"))
        assertNull(NameFixer.fixTelegramUnderscore("photo_2024-01-01_12-00-00.jpg"))
        assertNull(NameFixer.fixTelegramUnderscore("이미 공백 있음_파일.txt"))
        assertNull(NameFixer.fixTelegramUnderscore("noscore.txt"))
        assertTrue(NameFixer.isTelegramPath("/storage/emulated/0/Download/Telegram/a.txt"))
        assertTrue(NameFixer.isTelegramPath("/storage/emulated/0/Android/media/org.telegram.messenger/Telegram/Telegram Documents/a.txt"))
        assertTrue(!NameFixer.isTelegramPath("/storage/emulated/0/Download/a_b.txt"))
    }

    @Test fun cleanupFromBinder() {
        assertEquals("[작가] 제목 1권", NameFixer.cleanup("  [작가]  제목 ()  1권 "))
        assertEquals("제목 - 부제", NameFixer.cleanup("제목 -- _ 부제"))
        assertEquals("제목 (외전)", NameFixer.cleanup("제목 ( 외전 )"))
    }

    @Test fun unifyEpisode() {
        assertEquals("제목 12화", NameFixer.unifyEpisode("제목 12회차"))
        assertEquals("제목 1-216화", NameFixer.unifyEpisode("제목 1~216화"))
        assertEquals("12화 시작", NameFixer.unifyEpisode("#12 시작"))
        assertEquals("제목 3권", NameFixer.unifyEpisode("제목 03권"))
    }

    @Test fun planAutoFixDeepestFirstAndSkipsConflicts() {
        val items = listOf(
            Triple("/s/Download/Telegram/${nfd("폴더")}", nfd("폴더"), true),
            Triple("/s/Download/Telegram/${nfd("폴더")}/a_b.txt", "a_b.txt", false),
            Triple("/s/Download/Telegram/c_d.txt", "c_d.txt", false),
            Triple("/s/Download/e_f.txt", "e_f.txt", false),
        )
        val plan = NameFixer.planAutoFix(items, jamo = true, telegram = true) { dir ->
            if (dir.path == "/s/Download/Telegram") listOf(nfd("폴더"), "c_d.txt", "C D.txt") else emptyList()
        }
        // c_d.txt 는 "C D.txt" 가 이미 있어서 건너뜀, e_f.txt 는 텔레그램 폴더 아님
        assertEquals(listOf("a b.txt", "폴더"), plan.map { it.newName })
        assertEquals(NameFixer.Reason.JAMO, plan[1].reason)
        assertEquals(File("/s/Download/Telegram/${nfd("폴더")}/a_b.txt"), plan[0].file)
    }
}
