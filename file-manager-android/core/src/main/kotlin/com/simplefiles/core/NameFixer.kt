package com.simplefiles.core

import java.io.File
import java.text.Normalizer

/**
 * 파일명 자동 교정 규칙.
 * - 자소 분리(NFD) → 완성형(NFC)
 * - 텔레그램이 공백을 언더바로 바꿔 저장한 이름 되돌리기
 * - (EPUB 바인더 이름 변경에서 가져온) 빈 괄호/공백/구분자 정리, 화수 표기 통일
 */
object NameFixer {

    // ---------------- 자소 분리 ----------------

    fun hasSplitJamo(name: String): Boolean = !Normalizer.isNormalized(name, Normalizer.Form.NFC)

    fun fixJamo(name: String): String = TextNorm.nfc(name)

    // ---------------- 텔레그램 언더바 ----------------

    /** 카메라/텔레그램 미디어 자동 이름 (IMG_2024…, photo_2024-…, VID_…) 은 건드리지 않는다 */
    private val AUTO_MEDIA_NAME = Regex("^[A-Za-z]{2,12}[_-]\\d")
    private val NUM_RANGE = Regex("(?<!\\d)(?<!\\d_)(\\d{1,5})_(\\d{1,5})(?!\\d)(?!_\\d)")

    fun isTelegramPath(path: String): Boolean {
        val segs = path.split('/')
        return segs.any { it == "Telegram" || it.startsWith("Telegram ") || it == "org.telegram.messenger" }
    }

    /** 텔레그램식 언더바 이름이면 고친 이름, 아니면 null */
    fun fixTelegramUnderscore(name: String, isDir: Boolean = false): String? {
        val (base, ext) = if (isDir) name to "" else NameUtil.splitExt(name)
        if (!base.contains('_') || base.contains(' ')) return null
        if (AUTO_MEDIA_NAME.containsMatchIn(base)) return null
        val fixed = underscoresToSpaces(base)
        if (fixed.isEmpty() || fixed == base) return null
        return NameUtil.join(fixed, ext)
    }

    /** "내가_잘못했다면_1_216" → "내가 잘못했다면 1-216" */
    fun underscoresToSpaces(base: String): String {
        var t = NUM_RANGE.replace(base) { "${it.groupValues[1]}-${it.groupValues[2]}" }
        t = t.replace('_', ' ')
        return t.replace(Regex("\\s+"), " ").trim()
    }

    // ---------------- 이름 정리 (바인더 _cleanup_rename_preview_name) ----------------

    private val EMPTY_BRACKETS = listOf(
        "\\(\\s*\\)", "\\[\\s*\\]", "\\{\\s*\\}", "（\\s*）", "［\\s*］", "｛\\s*｝",
        "〈\\s*〉", "《\\s*》", "「\\s*」", "『\\s*』", "【\\s*】",
    ).map { Regex(it) }

    /** 일괄 편집 후 남는 공백, 빈 괄호, 중복 구분자를 정리 (확장자 제외한 이름에 적용) */
    fun cleanup(stem: String): String {
        var s = stem.replace('\n', ' ').replace(Regex("\\s+"), " ").trim()
        for (r in EMPTY_BRACKETS) s = r.replace(s, " ")
        s = Regex("([(\\[{〈《「『【])\\s+").replace(s, "$1")
        s = Regex("\\s+([)\\]}〉》」』】])").replace(s, "$1")
        s = Regex("\\s+([,.;:!?])").replace(s, "$1")
        s = Regex("(?:\\s*[-_~]\\s*){2,}").replace(s, " - ")
        s = Regex("[-_~]{2,}").replace(s) { it.value.substring(0, 1) }
        s = s.replace(Regex("\\s+"), " ").trim()
        s = s.trim(' ', '.', '-', '_', '~')
        return s
    }

    // ---------------- 화수 표기 통일 ----------------

    private val EP_RANGE = Regex("(?<!\\d)(\\d{1,5})\\s*[-~～_]\\s*(\\d{1,5})\\s*(?:화|회차|회|話)")
    private val EP_SINGLE = Regex("(?<!\\d)(\\d{1,5})\\s*(?:회차|회|話)")
    private val EP_HASH = Regex("^[#＃]\\s*(\\d{1,5})(?=\\s|$)")

    /** "12회차" "12회" "12話" "#12" → "12화", "1~216화" → "1-216화", 앞자리 0 제거 */
    fun unifyEpisode(stem: String): String {
        var s = EP_RANGE.replace(stem) { "${it.groupValues[1].toInt()}-${it.groupValues[2].toInt()}화" }
        s = EP_SINGLE.replace(s) { "${it.groupValues[1].toInt()}화" }
        s = EP_HASH.replace(s) { "${it.groupValues[1].toInt()}화" }
        s = Regex("(?<!\\d)0+(\\d+)\\s*(화|권)").replace(s) { "${it.groupValues[1]}${it.groupValues[2]}" }
        return s
    }

    // ---------------- 자동 교정 계획 ----------------

    data class AutoFix(val file: File, val newName: String, val reason: Reason)

    enum class Reason { JAMO, TELEGRAM }

    /**
     * 자동 교정할 항목. 깊은 경로부터 정렬되어 있어 그대로 순서대로 바꾸면 된다.
     * @param items (경로, 이름, 폴더 여부)
     */
    fun planAutoFix(
        items: List<Triple<String, String, Boolean>>,
        jamo: Boolean,
        telegram: Boolean,
        ignore: Set<String> = emptySet(),
        siblings: (File) -> List<String> = { it.list()?.toList().orEmpty() },
    ): List<AutoFix> {
        val out = mutableListOf<AutoFix>()
        for ((path, name, isDir) in items) {
            if (path in ignore) continue
            var newName = name
            var reason: Reason? = null
            if (jamo && hasSplitJamo(newName)) {
                newName = fixJamo(newName)
                reason = Reason.JAMO
            }
            if (telegram && isTelegramPath(path)) {
                val cat = if (isDir) null else FileCategory.of(newName)
                if (cat != FileCategory.IMAGES && cat != FileCategory.VIDEOS) {
                    fixTelegramUnderscore(newName, isDir)?.let {
                        newName = it
                        if (reason == null) reason = Reason.TELEGRAM
                    }
                }
            }
            if (reason == null || newName == name) continue
            if (NameUtil.invalidReason(newName) != null) continue
            val parent = File(path).parentFile ?: continue
            // 같은 폴더에 (대소문자/자소 분리 무시하고) 같은 이름의 다른 항목이 있으면 건너뛴다
            val newKey = TextNorm.key(newName)
            if (siblings(parent).any { it != name && TextNorm.key(it) == newKey }) continue
            out += AutoFix(File(path), newName, reason!!)
        }
        return out.sortedByDescending { it.file.path.count { c -> c == '/' } }
    }
}
