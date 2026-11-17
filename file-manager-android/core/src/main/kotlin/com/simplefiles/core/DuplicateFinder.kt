package com.simplefiles.core

import kotlin.math.abs
import kotlin.math.floor
import kotlin.math.max

data class DupCandidate(
    val path: String,
    val name: String,
    val size: Long,
    val lastModified: Long,
)

data class DupOptions(
    /** 파일명 일치율 기준 (0.9 = 90%) */
    val threshold: Double = 0.9,
    /** 확장자가 같은 파일끼리만 비교 */
    val sameExtension: Boolean = true,
    /** "이름 (1)", "이름 - 복사본" 같은 사본 표기를 지우고 비교 */
    val ignoreCopyMarkers: Boolean = false,
    /** 둘 다 숫자가 있는데 숫자가 다르면(1권/2권, 01화/02화) 중복이 아님 */
    val excludeDifferentNumbers: Boolean = true,
)

data class DupMember(val file: DupCandidate, val similarity: Double)

data class DupGroup(val members: List<DupMember>)

/**
 * 파일명 유사도(편집 거리 기반 일치율)로 중복 후보를 묶는다.
 * 일치율 = 1 - 편집거리 / 긴 이름의 글자 수 (확장자 제외, NFC/소문자/구분자 정규화 후)
 * A~B, B~C가 비슷하면 A, B, C를 한 묶음으로 본다.
 */
object DuplicateFinder {

    private val COPY_MARKERS = listOf(
        Regex("\\s*[(\\[]\\d{1,3}[)\\]]$"),
        Regex("\\s*-\\s*(복사본|사본|copy)(\\s*\\(\\d+\\))?$"),
        Regex("[\\s_]+(복사본|사본|copy)(\\s*\\d+)?$"),
    )
    private val SEPARATORS = Regex("[\\s_\\-.]+")
    private val DIGITS = Regex("\\d+")

    fun normalize(name: String, ignoreCopyMarkers: Boolean): String {
        var base = TextNorm.key(NameUtil.splitExt(name).first)
        if (ignoreCopyMarkers) {
            repeat(3) {
                for (r in COPY_MARKERS) base = r.replace(base, "")
            }
        }
        return SEPARATORS.replace(base, " ").trim()
    }

    /** 0.0 ~ 1.0 */
    fun similarity(a: String, b: String): Double {
        val m = max(a.length, b.length)
        if (m == 0) return 1.0
        return 1.0 - levenshtein(a, b, m).toDouble() / m
    }

    /** [limit]를 넘으면 limit+1을 돌려주는 편집 거리 */
    fun levenshtein(a: String, b: String, limit: Int): Int {
        if (a == b) return 0
        val n = a.length
        val m = b.length
        if (abs(n - m) > limit) return limit + 1
        if (n == 0) return m
        if (m == 0) return n
        var prev = IntArray(m + 1) { it }
        var cur = IntArray(m + 1)
        for (i in 1..n) {
            cur[0] = i
            var rowMin = i
            val ca = a[i - 1]
            for (j in 1..m) {
                val cost = if (ca == b[j - 1]) 0 else 1
                val v = minOf(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + cost)
                cur[j] = v
                if (v < rowMin) rowMin = v
            }
            if (rowMin > limit) return limit + 1
            val t = prev
            prev = cur
            cur = t
        }
        return if (prev[m] > limit) limit + 1 else prev[m]
    }

    private fun numbersOf(s: String): List<String> = DIGITS.findAll(s).map { it.value.trimStart('0').ifEmpty { "0" } }.toList()

    fun isSimilar(a: String, b: String, options: DupOptions): Boolean {
        if (options.excludeDifferentNumbers) {
            val na = numbersOf(a)
            val nb = numbersOf(b)
            if (na.isNotEmpty() && nb.isNotEmpty() && na != nb) return false
        }
        if (a == b) return true
        val m = max(a.length, b.length)
        val allowed = floor((1.0 - options.threshold) * m + 1e-9).toInt()
        return levenshtein(a, b, allowed) <= allowed
    }

    fun find(
        candidates: List<DupCandidate>,
        options: DupOptions = DupOptions(),
        onProgress: (Float) -> Unit = {},
        isCancelled: () -> Boolean = { false },
    ): List<DupGroup> {
        // 1) 정규화 이름이 같은 것끼리 먼저 묶어 비교 횟수를 줄인다.
        data class Key(val ext: String, val norm: String)
        val byKey = LinkedHashMap<Key, MutableList<Int>>()
        candidates.forEachIndexed { i, c ->
            val norm = normalize(c.name, options.ignoreCopyMarkers)
            if (norm.isEmpty()) return@forEachIndexed
            val ext = if (options.sameExtension) NameUtil.ext(c.name) else ""
            byKey.getOrPut(Key(ext, norm)) { mutableListOf() }.add(i)
        }
        val keys = byKey.keys.toList()
        val parent = IntArray(keys.size) { it }
        fun findRoot(x: Int): Int {
            var r = x
            while (parent[r] != r) {
                parent[r] = parent[parent[r]]
                r = parent[r]
            }
            return r
        }
        fun union(a: Int, b: Int) {
            val ra = findRoot(a)
            val rb = findRoot(b)
            if (ra != rb) parent[rb] = ra
        }

        // 2) 확장자별로, 이름 길이순 정렬 후 길이 차가 허용 범위 안인 것만 비교
        val buckets = keys.indices.groupBy { keys[it].ext }
        val total = keys.size.coerceAtLeast(1)
        var processed = 0
        if (options.threshold < 1.0) {
            for ((_, idxs) in buckets) {
                val sorted = idxs.sortedBy { keys[it].norm.length }
                for (x in sorted.indices) {
                    if (isCancelled()) return emptyList()
                    val a = keys[sorted[x]].norm
                    for (y in x + 1 until sorted.size) {
                        val b = keys[sorted[y]].norm
                        if (b.length - a.length > (1.0 - options.threshold) * b.length + 1e-9) break
                        if (findRoot(sorted[x]) == findRoot(sorted[y])) continue
                        if (isSimilar(a, b, options)) union(sorted[x], sorted[y])
                    }
                    processed++
                    if (processed % 200 == 0) onProgress(processed.toFloat() / total)
                }
            }
        }
        onProgress(1f)

        // 3) 묶음 만들기
        val groups = LinkedHashMap<Int, MutableList<Int>>()
        keys.indices.forEach { k -> groups.getOrPut(findRoot(k)) { mutableListOf() }.addAll(byKey[keys[k]]!!) }
        return groups.values
            .filter { it.size >= 2 }
            .map { members ->
                val files = members.map { candidates[it] }.sortedByDescending { it.lastModified }
                val ref = normalize(files.first().name, options.ignoreCopyMarkers)
                DupGroup(files.map { DupMember(it, similarity(ref, normalize(it.name, options.ignoreCopyMarkers))) })
            }
            .sortedWith(compareByDescending<DupGroup> { it.members.size }.thenBy { it.members.first().file.name })
    }
}
