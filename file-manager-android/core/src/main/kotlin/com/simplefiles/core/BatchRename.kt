package com.simplefiles.core

import java.io.File
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale
import java.util.UUID
import java.util.regex.PatternSyntaxException

data class RenameInput(
    val path: String,
    val name: String,
    val isDirectory: Boolean,
    val lastModified: Long = 0L,
) {
    val parent: String get() = File(path).parent ?: ""
    val parentName: String get() = File(parent).name
}

data class RenameContext(val index: Int, val input: RenameInput)

enum class TextPosition(val label: String) { START("앞"), END("뒤"), INDEX("위치 지정") }
enum class CaseMode(val label: String) { LOWER("소문자"), UPPER("대문자"), TITLE("단어 첫 글자 대문자"), SENTENCE("첫 글자만 대문자") }

/** 배치 네이머/이지네이머식 규칙. 위에서부터 순서대로 적용된다. */
sealed class RenameRule {
    abstract val enabled: Boolean
    abstract val title: String

    /** 이름(확장자 제외 또는 포함)에 적용 */
    open fun applyName(name: String, ctx: RenameContext): String = name

    /** 확장자에 적용 (확장자 포함 모드나 폴더에선 호출되지 않음) */
    open fun applyExt(ext: String, ctx: RenameContext): String = ext

    abstract fun withEnabled(on: Boolean): RenameRule

    /** 찾아 바꾸기 (정규식 지원: $1, $2 그룹 참조) */
    data class Replace(
        val find: String = "",
        val replacement: String = "",
        val regex: Boolean = false,
        val ignoreCase: Boolean = true,
        override val enabled: Boolean = true,
    ) : RenameRule() {
        override val title get() = "찾아 바꾸기"
        override fun withEnabled(on: Boolean) = copy(enabled = on)

        fun compiled(): Regex {
            val opts = if (ignoreCase) setOf(RegexOption.IGNORE_CASE) else emptySet()
            return if (regex) Regex(find, opts) else Regex(Regex.escape(find), opts)
        }

        override fun applyName(name: String, ctx: RenameContext): String {
            if (find.isEmpty()) return name
            val rep = if (regex) replacement else Regex.escapeReplacement(replacement)
            return compiled().replace(name, rep)
        }
    }

    /** 글자 넣기 */
    data class Insert(
        val text: String = "",
        val position: TextPosition = TextPosition.START,
        val index: Int = 0,
        override val enabled: Boolean = true,
    ) : RenameRule() {
        override val title get() = "글자 넣기"
        override fun withEnabled(on: Boolean) = copy(enabled = on)
        override fun applyName(name: String, ctx: RenameContext): String = when (position) {
            TextPosition.START -> text + name
            TextPosition.END -> name + text
            TextPosition.INDEX -> {
                val i = index.coerceIn(0, name.length)
                name.substring(0, i) + text + name.substring(i)
            }
        }
    }

    /** 글자 지우기: [start]번째(0부터)에서 [count]글자. [fromEnd]면 뒤에서부터 센다. */
    data class Remove(
        val start: Int = 0,
        val count: Int = 1,
        val fromEnd: Boolean = false,
        override val enabled: Boolean = true,
    ) : RenameRule() {
        override val title get() = "글자 지우기"
        override fun withEnabled(on: Boolean) = copy(enabled = on)
        override fun applyName(name: String, ctx: RenameContext): String {
            if (count <= 0) return name
            val len = name.length
            val (s, e) = if (!fromEnd) {
                val s = start.coerceIn(0, len)
                s to (s + count).coerceAtMost(len)
            } else {
                val e = (len - start).coerceIn(0, len)
                (e - count).coerceAtLeast(0) to e
            }
            return name.removeRange(s, e)
        }
    }

    /** 번호 붙이기 */
    data class Numbering(
        val start: Int = 1,
        val step: Int = 1,
        val digits: Int = 2,
        val position: TextPosition = TextPosition.START,
        val separator: String = "_",
        override val enabled: Boolean = true,
    ) : RenameRule() {
        override val title get() = "번호 붙이기"
        override fun withEnabled(on: Boolean) = copy(enabled = on)
        fun number(index: Int): String = (start + index * step).toString().padStart(digits.coerceIn(1, 9), '0')
        override fun applyName(name: String, ctx: RenameContext): String {
            val n = number(ctx.index)
            return when (position) {
                TextPosition.END -> name + separator + n
                else -> n + separator + name
            }
        }
    }

    /**
     * 새 이름 틀: {name} 현재 이름, {n} 번호(1부터), {n:3} 자릿수 지정, {parent} 상위 폴더명, {date} 수정일(yyyyMMdd)
     * 예) "{parent}_{n:3}"
     */
    data class Template(
        val pattern: String = "{name}",
        val start: Int = 1,
        override val enabled: Boolean = true,
    ) : RenameRule() {
        override val title get() = "이름 틀"
        override fun withEnabled(on: Boolean) = copy(enabled = on)
        override fun applyName(name: String, ctx: RenameContext): String {
            val fmt = SimpleDateFormat("yyyyMMdd", Locale.ROOT)
            return TOKEN.replace(pattern) { m ->
                when (m.groupValues[1]) {
                    "name" -> name
                    "parent" -> ctx.input.parentName
                    "date" -> fmt.format(Date(ctx.input.lastModified))
                    "n" -> {
                        val d = m.groupValues[2].toIntOrNull() ?: 1
                        (start + ctx.index).toString().padStart(d.coerceIn(1, 9), '0')
                    }
                    else -> m.value
                }
            }
        }

        companion object {
            private val TOKEN = Regex("\\{(name|parent|date|n)(?::(\\d+))?\\}")
        }
    }

    /** 대소문자 */
    data class ChangeCase(
        val mode: CaseMode = CaseMode.LOWER,
        override val enabled: Boolean = true,
    ) : RenameRule() {
        override val title get() = "대소문자"
        override fun withEnabled(on: Boolean) = copy(enabled = on)
        override fun applyName(name: String, ctx: RenameContext): String = when (mode) {
            CaseMode.LOWER -> name.lowercase()
            CaseMode.UPPER -> name.uppercase()
            CaseMode.TITLE -> name.split(" ").joinToString(" ") { w -> w.replaceFirstChar { it.uppercaseChar() } }
            CaseMode.SENTENCE -> name.lowercase().replaceFirstChar { it.uppercaseChar() }
        }
    }

    /** 덮어쓰기: 이름 전체를 새 이름으로 (바인더 '덮어쓰기') */
    data class Overwrite(
        val newName: String = "",
        override val enabled: Boolean = true,
    ) : RenameRule() {
        override val title get() = "덮어쓰기"
        override fun withEnabled(on: Boolean) = copy(enabled = on)
        override fun applyName(name: String, ctx: RenameContext): String = newName.ifBlank { name }
    }

    /** 뒤에 화수 붙이기 (바인더): 기존 끝의 "N화/N권"을 지우고 " 1화", " 2화"… 를 붙인다 */
    data class EpisodeSuffix(
        val start: Int = 1,
        val step: Int = 1,
        val unit: String = "화",
        override val enabled: Boolean = true,
    ) : RenameRule() {
        override val title get() = "뒤에 화수 붙이기"
        override fun withEnabled(on: Boolean) = copy(enabled = on)
        override fun applyName(name: String, ctx: RenameContext): String {
            val n = start + ctx.index * step
            val stripped = TRAILING.replace(name, "").trim()
            return "$stripped $n$unit".trim()
        }

        companion object {
            private val TRAILING = Regex("\\s*\\d+\\s*[화권]\\s*$")
        }
    }

    /** 확장자 바꾸기 (빈칸이면 확장자 제거) */
    data class Extension(
        val newExt: String = "",
        override val enabled: Boolean = true,
    ) : RenameRule() {
        override val title get() = "확장자 바꾸기"
        override fun withEnabled(on: Boolean) = copy(enabled = on)
        override fun applyExt(ext: String, ctx: RenameContext): String = newExt.trim().trimStart('.')
    }
}

/** 규칙 적용 뒤 후처리 (EPUB 바인더 일괄 변경 옵션) */
data class RenamePostOptions(
    /** 빈 괄호, 중복 공백, 겹친 구분자 정리 */
    val cleanup: Boolean = false,
    /** "12회차/12회/#12" → "12화", "1~216화" → "1-216화" */
    val unifyEpisode: Boolean = false,
    /** 자소 분리(NFD) 한글을 완성형으로 */
    val fixJamo: Boolean = false,
    /** 언더바를 공백으로 (텔레그램) */
    val underscoreToSpace: Boolean = false,
) {
    val any: Boolean get() = cleanup || unifyEpisode || fixJamo || underscoreToSpace

    companion object {
        val NONE = RenamePostOptions()
        val RECOMMENDED = RenamePostOptions(cleanup = true, unifyEpisode = true, fixJamo = true)
    }
}

data class RenamePreview(
    val input: RenameInput,
    val newName: String,
    val error: String?,
    /** 적용 범위에서 빠진 항목 */
    val excluded: Boolean = false,
) {
    val changed: Boolean get() = newName != input.name
}

data class RenamePlan(val previews: List<RenamePreview>, val ruleError: String?) {
    val hasErrors: Boolean get() = ruleError != null || previews.any { it.error != null }
    val changes: List<RenamePreview> get() = previews.filter { it.changed && it.error == null && !it.excluded }
}

object BatchRenamer {

    /**
     * 미리보기 계산.
     * @param includeExtension true면 규칙을 확장자까지 포함한 전체 이름에 적용
     * @param exists 다른 파일 존재 여부 확인 (테스트 주입용)
     */
    fun plan(
        inputs: List<RenameInput>,
        rules: List<RenameRule>,
        includeExtension: Boolean,
        exists: (File) -> Boolean = { it.exists() },
        post: RenamePostOptions = RenamePostOptions.NONE,
        /** 적용할 항목 경로 (null = 전체). 번호는 적용 항목끼리만 센다. */
        included: Set<String>? = null,
    ): RenamePlan {
        val active = rules.filter { it.enabled }
        var ruleError: String? = null
        for (r in active) {
            if (r is RenameRule.Replace && r.regex && r.find.isNotEmpty()) {
                try {
                    r.compiled()
                } catch (e: PatternSyntaxException) {
                    ruleError = "정규식 오류: ${e.description}"
                }
            }
        }
        if (ruleError != null) {
            return RenamePlan(inputs.map { RenamePreview(it, it.name, null) }, ruleError)
        }

        var order = 0
        val raw = inputs.map { input ->
            if (included != null && input.path !in included) {
                return@map RenamePreview(input, input.name, null, excluded = true)
            }
            val ctx = RenameContext(order++, input)
            try {
                RenamePreview(input, compute(input, active, includeExtension, ctx, post), null)
            } catch (e: Exception) {
                // 잘못된 그룹 참조($3 등) 같은 치환 오류
                ruleError = "규칙 오류: ${e.message}"
                RenamePreview(input, input.name, null)
            }
        }
        if (ruleError != null) return RenamePlan(raw, ruleError)

        // 같은 폴더 안에서 결과 이름 중복 검사 (안드로이드 저장소는 대소문자 구분 없음)
        val renamedKeys = raw.groupBy { it.input.parent to TextNorm.key(it.newName) }
        val originalKeys = inputs.map { it.parent to TextNorm.key(it.name) }.toSet()

        val previews = raw.map { p ->
            if (p.excluded) return@map p
            val invalid = NameUtil.invalidReason(p.newName)
            val error = when {
                invalid != null -> invalid
                (renamedKeys[p.input.parent to TextNorm.key(p.newName)]?.size ?: 0) > 1 -> "결과 이름이 겹칩니다"
                p.changed &&
                    (p.input.parent to TextNorm.key(p.newName)) !in originalKeys &&
                    exists(File(p.input.parent, p.newName)) -> "같은 이름의 파일이 이미 있습니다"
                else -> null
            }
            p.copy(error = error)
        }
        return RenamePlan(previews, null)
    }

    private fun compute(
        input: RenameInput,
        rules: List<RenameRule>,
        includeExt: Boolean,
        ctx: RenameContext,
        post: RenamePostOptions,
    ): String {
        val split = !includeExt && !input.isDirectory
        var (base, ext) = if (split) NameUtil.splitExt(input.name) else input.name to ""
        for (r in rules) {
            base = r.applyName(base, ctx)
            if (split) ext = r.applyExt(ext, ctx)
        }
        if (post.fixJamo) {
            base = NameFixer.fixJamo(base)
            ext = NameFixer.fixJamo(ext)
        }
        if (post.underscoreToSpace) base = NameFixer.underscoresToSpaces(base)
        if (post.unifyEpisode) base = NameFixer.unifyEpisode(base)
        if (post.cleanup) base = NameFixer.cleanup(base).ifEmpty { base }
        return NameUtil.join(base, ext)
    }

    data class Applied(val from: File, val to: File)

    data class ExecuteResult(val applied: List<Applied>, val failures: List<Pair<String, String>>)

    /**
     * 2단계 이름 바꾸기: 먼저 모두 임시 이름으로 바꾼 뒤 최종 이름으로 바꾼다.
     * a->b, b->a 같은 맞바꾸기나 대소문자만 바꾸는 경우도 안전하다.
     */
    fun execute(changes: List<Pair<File, String>>): ExecuteResult {
        val staged = mutableListOf<Triple<File, File, File>>() // original, temp, final
        val failures = mutableListOf<Pair<String, String>>()
        for ((src, newName) in changes) {
            val tmp = File(src.parentFile, ".rename_${UUID.randomUUID().toString().take(12)}")
            if (src.renameTo(tmp)) staged += Triple(src, tmp, File(src.parentFile, newName))
            else failures += src.path to "이름을 바꿀 수 없습니다"
        }
        val applied = mutableListOf<Applied>()
        for ((orig, tmp, final) in staged) {
            if (!final.exists() && tmp.renameTo(final)) {
                applied += Applied(orig, final)
            } else {
                tmp.renameTo(orig)
                failures += orig.path to "'${final.name}'(으)로 바꿀 수 없습니다"
            }
        }
        return ExecuteResult(applied, failures)
    }

    /** 되돌리기: 적용 결과를 반대로 실행 */
    fun undo(applied: List<Applied>): ExecuteResult =
        execute(applied.map { it.to to it.from.name })
}
