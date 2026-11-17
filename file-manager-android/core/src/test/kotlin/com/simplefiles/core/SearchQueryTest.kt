package com.simplefiles.core

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test
import java.text.Normalizer

class SearchQueryTest {
    private fun m(q: String, name: String) = SearchQuery(q).matches(TextNorm.key(name))

    @Test fun partialPrefixMatches() {
        assertTrue(m("내가", "내가 잘못했다면.txt"))
        assertTrue(m("잘못", "내가 잘못했다면.txt"))
    }

    @Test fun tokensAnyOrderAndNoSpace() {
        assertTrue(m("잘못 내가", "내가 잘못했다면"))
        assertTrue(m("내가잘못", "내가 잘못했다면"))
        assertFalse(m("내가 너는", "내가 잘못했다면"))
    }

    @Test fun caseInsensitive() {
        assertTrue(m("READ", "readme.MD"))
    }

    @Test fun nfdFileNameMatches() {
        val nfd = Normalizer.normalize("내가 잘못했다면", Normalizer.Form.NFD)
        assertTrue(m("내가", nfd))
    }

    @Test fun chosungSearch() {
        assertTrue(m("ㄴㄱ", "내가 잘못했다면"))
        assertTrue(m("ㅈㅁㅎ", "내가 잘못했다면"))
        assertFalse(m("ㅎㄱ", "내가 잘못했다면"))
    }

    @Test fun emptyQueryMatchesNothing() {
        assertFalse(m("   ", "abc"))
    }

    @Test fun rankPrefersPrefix() {
        val q = SearchQuery("내가")
        assertTrue(q.rank(TextNorm.key("내가 잘못")) < q.rank(TextNorm.key("그래 내가")))
        assertEquals(0..1, q.highlight("내가 잘못"))
    }
}
