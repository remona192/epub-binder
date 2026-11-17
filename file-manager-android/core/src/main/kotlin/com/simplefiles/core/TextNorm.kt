package com.simplefiles.core

import java.text.Normalizer
import java.util.Locale

/** 파일명 비교용 정규화. 맥/일부 앱이 만든 NFD(자모 분리) 한글 파일명도 같은 글자로 취급한다. */
object TextNorm {
    fun nfc(s: String): String =
        if (Normalizer.isNormalized(s, Normalizer.Form.NFC)) s else Normalizer.normalize(s, Normalizer.Form.NFC)

    /** 검색/비교 키: NFC + 소문자. */
    fun key(s: String): String = nfc(s).lowercase(Locale.ROOT)

    private const val CHOSUNG = "ㄱㄲㄴㄷㄸㄹㅁㅂㅃㅅㅆㅇㅈㅉㅊㅋㅌㅍㅎ"

    /** "내가 잘못했다면" -> "ㄴㄱ ㅈㅁㅎㄷㅁ" */
    fun chosung(s: String): String {
        val sb = StringBuilder(s.length)
        for (c in s) {
            if (c in '\uAC00'..'\uD7A3') sb.append(CHOSUNG[(c - '\uAC00') / 588]) else sb.append(c)
        }
        return sb.toString()
    }

    fun isChosungOnly(s: String): Boolean = s.isNotEmpty() && s.all { it in CHOSUNG }
}

/**
 * 파일명 검색 질의.
 * - 대소문자 무시, NFC 정규화
 * - 공백으로 나눈 단어가 모두 포함되면 일치 (순서 무관): "잘못 내가" 도 "내가 잘못했다면"에 일치
 * - 공백 무시 일치: "내가잘못" 도 일치
 * - 초성 검색: "ㄴㄱ" 도 일치
 */
class SearchQuery(raw: String) {
    val tokens: List<String> = TextNorm.key(raw).trim().split(Regex("\\s+")).filter { it.isNotEmpty() }
    private val needChosung = tokens.any { TextNorm.isChosungOnly(it) }

    val isEmpty: Boolean get() = tokens.isEmpty()

    /** [nameKey]는 [TextNorm.key]로 만든 값. */
    fun matches(nameKey: String): Boolean {
        if (tokens.isEmpty()) return false
        var noSpace: String? = null
        var cho: String? = null
        for (t in tokens) {
            if (nameKey.contains(t)) continue
            val ns = noSpace ?: nameKey.replace(" ", "").also { noSpace = it }
            if (ns.contains(t)) continue
            if (needChosung && TextNorm.isChosungOnly(t)) {
                val c = cho ?: TextNorm.chosung(ns).also { cho = it }
                if (c.contains(t)) continue
            }
            return false
        }
        return true
    }

    /** 정렬용 점수: 낮을수록 위. 0=완전일치, 1=앞부분 일치, 2=단어 시작 일치, 3=기타 */
    fun rank(nameKey: String): Int {
        val first = tokens.firstOrNull() ?: return 3
        return when {
            nameKey == first -> 0
            nameKey.startsWith(first) -> 1
            nameKey.contains(" $first") || nameKey.contains("_$first") -> 2
            else -> 3
        }
    }

    /** 표시용 강조 범위 (첫 단어 기준). 없으면 null. */
    fun highlight(displayName: String): IntRange? {
        val first = tokens.firstOrNull() ?: return null
        val k = TextNorm.key(displayName)
        if (k.length != displayName.length) return null
        val i = k.indexOf(first)
        return if (i >= 0) i until i + first.length else null
    }
}
