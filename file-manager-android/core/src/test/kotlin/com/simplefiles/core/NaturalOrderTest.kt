package com.simplefiles.core

import org.junit.Assert.assertEquals
import org.junit.Test

class NaturalOrderTest {
    @Test fun numbersSortNumerically() {
        val sorted = listOf("책 10권", "책 2권", "책 1권", "Apple", "apple 2", "banana").sortedWith(NaturalOrder)
        assertEquals(listOf("Apple", "apple 2", "banana", "책 1권", "책 2권", "책 10권"), sorted)
    }
}
