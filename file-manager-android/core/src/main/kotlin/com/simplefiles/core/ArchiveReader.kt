package com.simplefiles.core

import org.apache.commons.compress.archivers.sevenz.SevenZFile
import org.apache.commons.compress.archivers.zip.UnicodePathExtraField
import org.apache.commons.compress.archivers.zip.ZipArchiveEntry
import org.apache.commons.compress.archivers.zip.ZipFile
import java.io.File
import java.io.InputStream
import java.nio.ByteBuffer
import java.nio.charset.CharacterCodingException
import java.nio.charset.Charset
import java.nio.charset.CodingErrorAction

/** 압축 파일 안의 항목 (경로 구분자는 '/') */
data class ArchiveItem(
    val path: String,
    val isDirectory: Boolean,
    val size: Long,
    val lastModified: Long,
) {
    val name: String get() = path.trimEnd('/').substringAfterLast('/')
    val parent: String get() = path.trimEnd('/').substringBeforeLast('/', "")
}

/**
 * zip / 7z 안의 파일 목록 읽기와 꺼내기.
 * 윈도우에서 만든 zip의 CP949(한글) 파일명도 자동 판별한다.
 */
object ArchiveReader {
    val SUPPORTED_EXTS = setOf("zip", "7z", "cbz")

    fun isSupported(name: String): Boolean = NameUtil.ext(name) in SUPPORTED_EXTS

    private val koreanCharset: Charset? by lazy {
        listOf("MS949", "x-windows-949", "windows-949", "EUC-KR")
            .firstNotNullOfOrNull { runCatching { Charset.forName(it) }.getOrNull() }
    }

    private fun strictUtf8(bytes: ByteArray): String? = try {
        Charsets.UTF_8.newDecoder()
            .onMalformedInput(CodingErrorAction.REPORT)
            .onUnmappableCharacter(CodingErrorAction.REPORT)
            .decode(ByteBuffer.wrap(bytes)).toString()
    } catch (e: CharacterCodingException) {
        null
    }

    private fun zipName(e: ZipArchiveEntry): String {
        if (e.generalPurposeBit.usesUTF8ForNames()) return e.name
        if (e.getExtraField(UnicodePathExtraField.UPATH_ID) != null) return e.name
        val raw = e.rawName ?: return e.name
        if (raw.all { it >= 0 }) return e.name // ASCII
        strictUtf8(raw)?.let { return it }
        return koreanCharset?.let { String(raw, it) } ?: e.name
    }

    private fun openZip(file: File): ZipFile =
        ZipFile.builder().setFile(file).setCharset(Charsets.UTF_8).setUseUnicodeExtraFields(true).get()

    private fun openSevenZ(file: File): SevenZFile = SevenZFile.builder().setFile(file).get()

    /**
     * 항목 목록. 폴더 항목이 따로 없어도 경로에서 폴더를 만들어 넣는다.
     * 암호가 걸렸거나 손상된 파일은 빈 목록.
     */
    fun list(file: File, maxEntries: Int = 50_000): List<ArchiveItem> {
        val items = LinkedHashMap<String, ArchiveItem>()
        try {
            when (NameUtil.ext(file.name)) {
                "zip", "cbz" -> openZip(file).use { zf ->
                    for (e in zf.entries) {
                        if (items.size >= maxEntries) break
                        val p = TextNorm.nfc(zipName(e)).replace('\\', '/').trim('/')
                        if (p.isEmpty()) continue
                        items[p] = ArchiveItem(p, e.isDirectory, if (e.isDirectory) 0 else e.size.coerceAtLeast(0), e.time)
                    }
                }
                "7z" -> openSevenZ(file).use { sz ->
                    for (e in sz.entries) {
                        if (items.size >= maxEntries) break
                        val p = TextNorm.nfc(e.name ?: continue).replace('\\', '/').trim('/')
                        if (p.isEmpty()) continue
                        val t = if (e.hasLastModifiedDate) e.lastModifiedDate.time else 0L
                        items[p] = ArchiveItem(p, e.isDirectory, if (e.isDirectory) 0 else e.size, t)
                    }
                }
                else -> return emptyList()
            }
        } catch (e: Exception) {
            return emptyList()
        } catch (e: OutOfMemoryError) {
            return emptyList()
        }
        // 빠진 상위 폴더 채우기
        for (item in items.values.toList()) {
            var parent = item.parent
            while (parent.isNotEmpty() && parent !in items) {
                items[parent] = ArchiveItem(parent, true, 0, item.lastModified)
                parent = parent.substringBeforeLast('/', "")
            }
        }
        return items.values.toList()
    }

    /** [entryPath] 파일을 [dest]로 꺼낸다 */
    fun extract(file: File, entryPath: String, dest: File): Boolean {
        dest.parentFile?.mkdirs()
        return try {
            when (NameUtil.ext(file.name)) {
                "zip", "cbz" -> openZip(file).use { zf ->
                    val entry = zf.entries.asSequence().firstOrNull { normalized(zipName(it)) == entryPath } ?: return false
                    zf.getInputStream(entry).use { copyTo(it, dest) }
                }
                "7z" -> openSevenZ(file).use { sz ->
                    val entry = sz.entries.firstOrNull { it.name != null && normalized(it.name) == entryPath } ?: return false
                    sz.getInputStream(entry).use { copyTo(it, dest) }
                }
                else -> false
            }
        } catch (e: Exception) {
            dest.delete()
            false
        }
    }

    private fun normalized(name: String) = TextNorm.nfc(name).replace('\\', '/').trim('/')

    private fun copyTo(input: InputStream, dest: File): Boolean {
        dest.outputStream().use { input.copyTo(it, 256 * 1024) }
        return true
    }
}
