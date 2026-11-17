package com.simplefiles.core

import java.io.File
import java.io.IOException

enum class TransferMode { COPY, MOVE }

/** 같은 이름이 있을 때의 선택 (삼성 내 파일: 건너뛰기 / 이름 변경 / 바꾸기). */
enum class ConflictChoice { SKIP, KEEP_BOTH, REPLACE }

data class ConflictDecision(val choice: ConflictChoice, val applyToAll: Boolean)

data class TransferProgress(val done: Int, val total: Int, val currentName: String)

data class TransferResult(
    val succeeded: Int,
    val skipped: Int,
    val failures: List<Pair<String, String>>,
    val cancelled: Boolean,
    /** 최상위 결과 경로들 (복사/이동된 위치) */
    val outputs: List<File>,
)

/**
 * 삼성 '내 파일' 방식의 복사/이동.
 * - 같은 폴더에 복사하면 자동으로 "이름 (1)" 사본을 만든다.
 * - 같은 폴더로 이동하면 아무것도 하지 않는다.
 * - 폴더를 자기 자신 또는 하위 폴더로 복사/이동할 수 없다.
 * - 이름이 겹치면 [onConflict]로 묻고, "모든 항목에 적용"을 기억한다.
 *   폴더끼리 '바꾸기'를 고르면 안의 내용을 합친다(병합).
 * - 이동은 같은 저장소면 rename으로 즉시, 아니면 복사 후 원본 삭제.
 */
class FileTransfer(
    private val onConflict: suspend (source: File, target: File) -> ConflictDecision,
    private val onProgress: (TransferProgress) -> Unit = {},
    private val isCancelled: () -> Boolean = { false },
) {
    private var remembered: ConflictChoice? = null
    private var done = 0
    private var total = 0
    private var succeeded = 0
    private var skipped = 0
    private val failures = mutableListOf<Pair<String, String>>()
    private var cancelled = false

    suspend fun run(sources: List<File>, destDir: File, mode: TransferMode): TransferResult {
        total = sources.sumOf { countFiles(it) }
        val outputs = mutableListOf<File>()
        if (!destDir.isDirectory) {
            return TransferResult(0, 0, listOf(destDir.path to "대상 폴더가 없습니다"), false, emptyList())
        }
        for (src in sources) {
            if (checkCancel()) break
            if (!src.exists()) {
                failures += src.path to "원본이 없습니다"
                continue
            }
            if (src.isDirectory && NameUtil.isInside(destDir, src)) {
                failures += src.path to "폴더를 자기 자신 또는 하위 폴더로 옮길 수 없습니다"
                continue
            }
            val sameDir = src.absoluteFile.parentFile?.normalize() == destDir.absoluteFile.normalize()
            if (sameDir && mode == TransferMode.MOVE) {
                skipped++
                continue
            }
            val target = if (sameDir) {
                File(destDir, NameUtil.uniqueName(destDir, src.name, src.isDirectory))
            } else {
                File(destDir, src.name)
            }
            val out = transferOne(src, target, mode)
            if (out != null) outputs += out
        }
        return TransferResult(succeeded, skipped, failures.toList(), cancelled, outputs)
    }

    private fun checkCancel(): Boolean {
        if (!cancelled && isCancelled()) cancelled = true
        return cancelled
    }

    private fun countFiles(f: File): Int {
        if (!f.isDirectory) return 1
        val children = f.listFiles() ?: return 1
        return children.sumOf { countFiles(it) }.coerceAtLeast(1)
    }

    private suspend fun transferOne(src: File, initialTarget: File, mode: TransferMode): File? {
        if (checkCancel()) return null
        var target = initialTarget
        if (target.exists()) {
            val choice = remembered ?: onConflict(src, target).also { if (it.applyToAll) remembered = it.choice }.choice
            when (choice) {
                ConflictChoice.SKIP -> {
                    val n = countFiles(src)
                    skipped += n
                    advance(n, src.name)
                    return null
                }
                ConflictChoice.KEEP_BOTH -> {
                    val dir = target.parentFile!!
                    target = File(dir, NameUtil.uniqueName(dir, src.name, src.isDirectory))
                }
                ConflictChoice.REPLACE -> {
                    if (src.isDirectory && target.isDirectory) {
                        return merge(src, target, mode)
                    }
                    if (src.isDirectory != target.isDirectory) {
                        // 파일 <-> 폴더 교체는 데이터 손실 위험이 커서 둘 다 남긴다.
                        val dir = target.parentFile!!
                        target = File(dir, NameUtil.uniqueName(dir, src.name, src.isDirectory))
                    } else if (!target.delete()) {
                        failures += src.path to "기존 파일을 바꿀 수 없습니다"
                        advance(1, src.name)
                        return null
                    }
                }
            }
        }

        if (mode == TransferMode.MOVE && src.renameTo(target)) {
            val n = countFilesAfterMove(target)
            succeeded += n
            advance(n, src.name)
            return target
        }
        return try {
            val ok = copyRecursive(src, target)
            if (ok && mode == TransferMode.MOVE) {
                if (!src.deleteRecursively()) failures += src.path to "원본을 삭제하지 못했습니다"
            }
            if (ok) target else null
        } catch (e: IOException) {
            failures += src.path to (e.message ?: "입출력 오류")
            null
        }
    }

    private fun countFilesAfterMove(f: File) = countFiles(f)

    /** 폴더끼리 '바꾸기' = 내용 병합. 하위 충돌도 같은 규칙으로 처리. */
    private suspend fun merge(srcDir: File, targetDir: File, mode: TransferMode): File {
        val children = srcDir.listFiles().orEmpty()
        for (child in children) {
            if (checkCancel()) break
            transferOne(child, File(targetDir, child.name), mode)
        }
        if (mode == TransferMode.MOVE && !cancelled) {
            if (srcDir.listFiles().isNullOrEmpty()) srcDir.delete()
        }
        return targetDir
    }

    private fun copyRecursive(src: File, target: File): Boolean {
        if (checkCancel()) return false
        if (src.isDirectory) {
            if (!target.exists() && !target.mkdirs()) {
                failures += src.path to "폴더를 만들 수 없습니다"
                return false
            }
            var allOk = true
            val children = src.listFiles().orEmpty()
            if (children.isEmpty()) {
                succeeded++
                advance(1, src.name)
            }
            for (c in children) {
                if (!copyRecursive(c, File(target, c.name))) allOk = false
                if (cancelled) return false
            }
            return allOk
        }
        val tmp = File(target.parentFile, ".${target.name}.part")
        try {
            src.inputStream().use { input ->
                tmp.outputStream().use { output ->
                    val buf = ByteArray(256 * 1024)
                    while (true) {
                        if (checkCancel()) break
                        val r = input.read(buf)
                        if (r < 0) break
                        output.write(buf, 0, r)
                    }
                }
            }
            if (cancelled) {
                tmp.delete()
                return false
            }
            if (!tmp.renameTo(target)) {
                tmp.delete()
                throw IOException("파일을 쓸 수 없습니다")
            }
            target.setLastModified(src.lastModified())
            succeeded++
            advance(1, src.name)
            return true
        } catch (e: IOException) {
            tmp.delete()
            failures += src.path to (e.message ?: "입출력 오류")
            advance(1, src.name)
            return false
        }
    }

    private fun advance(n: Int, name: String) {
        done += n
        onProgress(TransferProgress(done.coerceAtMost(total), total, name))
    }
}
