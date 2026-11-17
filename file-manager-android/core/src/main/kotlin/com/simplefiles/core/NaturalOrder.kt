package com.simplefiles.core

/** "2권" < "10권" 처럼 숫자를 수 크기로 비교하는 이름 정렬. 대소문자/NFD 무시. */
object NaturalOrder : Comparator<String> {
    override fun compare(x: String, y: String): Int {
        val a = TextNorm.key(x)
        val b = TextNorm.key(y)
        var i = 0
        var j = 0
        while (i < a.length && j < b.length) {
            val ca = a[i]
            val cb = b[j]
            if (ca.isDigit() && cb.isDigit()) {
                var ei = i
                while (ei < a.length && a[ei].isDigit()) ei++
                var ej = j
                while (ej < b.length && b[ej].isDigit()) ej++
                val na = a.substring(i, ei).trimStart('0')
                val nb = b.substring(j, ej).trimStart('0')
                if (na.length != nb.length) return na.length - nb.length
                val c = na.compareTo(nb)
                if (c != 0) return c
                i = ei
                j = ej
            } else {
                if (ca != cb) return ca.compareTo(cb)
                i++
                j++
            }
        }
        val rest = (a.length - i) - (b.length - j)
        return if (rest != 0) rest else x.compareTo(y)
    }
}
