package com.simplefiles.core

import java.io.File
import java.util.UUID

data class TrashEntry(
    val id: String,
    val originalPath: String,
    val deletedAt: Long,
    val stored: File,
) {
    val name: String get() = File(originalPath).name
    val isDirectory: Boolean get() = stored.isDirectory
}

/**
 * 휴지통. 삼성 '내 파일'처럼 삭제한 항목을 보관했다가 복원하거나 영구 삭제한다.
 * 저장소(내장/SD)마다 루트에 숨김 폴더를 만들어 같은 저장소 안에서 rename으로 즉시 옮긴다.
 */
class TrashStore(
    private val roots: () -> List<File>,
    private val now: () -> Long = System::currentTimeMillis,
) {
    companion object {
        const val DIR_NAME = ".SimpleFilesTrash"
        const val RETENTION_DAYS = 30
        private const val DAY_MS = 24L * 60 * 60 * 1000
    }

    private fun rootOf(file: File): File? =
        roots().filter { NameUtil.isInside(file, it) }.maxByOrNull { it.path.length }

    private fun trashDir(root: File) = File(root, DIR_NAME)

    fun isTrashPath(file: File): Boolean = roots().any { NameUtil.isInside(file, trashDir(it)) }

    fun moveToTrash(file: File): Boolean {
        val root = rootOf(file) ?: file.parentFile ?: return false
        val dir = trashDir(root)
        val filesDir = File(dir, "files").apply { mkdirs() }
        val metaDir = File(dir, "meta").apply { mkdirs() }
        File(dir, ".nomedia").let { if (!it.exists()) runCatching { it.createNewFile() } }
        val t = now()
        val id = "${t}_${UUID.randomUUID().toString().take(8)}"
        val stored = File(filesDir, id)
        val moved = file.renameTo(stored) || (file.copyRecursively(stored, overwrite = false) && file.deleteRecursively())
        if (!moved) {
            stored.deleteRecursively()
            return false
        }
        File(metaDir, "$id.txt").writeText("${file.absolutePath}\n$t\n")
        return true
    }

    fun list(): List<TrashEntry> {
        val out = mutableListOf<TrashEntry>()
        for (root in roots()) {
            val dir = trashDir(root)
            val metas = File(dir, "meta").listFiles() ?: continue
            for (m in metas) {
                if (!m.name.endsWith(".txt")) continue
                val id = m.name.removeSuffix(".txt")
                val lines = runCatching { m.readLines() }.getOrNull() ?: continue
                val stored = File(dir, "files/$id")
                if (!stored.exists()) {
                    m.delete()
                    continue
                }
                val path = lines.getOrNull(0) ?: continue
                val at = lines.getOrNull(1)?.toLongOrNull() ?: 0L
                out += TrashEntry(id, path, at, stored)
            }
        }
        return out.sortedByDescending { it.deletedAt }
    }

    fun daysLeft(entry: TrashEntry): Int {
        val left = RETENTION_DAYS - ((now() - entry.deletedAt) / DAY_MS).toInt()
        return left.coerceAtLeast(0)
    }

    /** 원래 위치로 복원. 이름이 겹치면 "이름 (1)"로 복원. 복원된 파일을 반환. */
    fun restore(entry: TrashEntry): File? {
        val original = File(entry.originalPath)
        val parent = original.parentFile ?: return null
        if (!parent.exists() && !parent.mkdirs()) return null
        val target = File(parent, NameUtil.uniqueName(parent, original.name, entry.stored.isDirectory))
        val ok = entry.stored.renameTo(target) ||
            (entry.stored.copyRecursively(target, overwrite = false) && entry.stored.deleteRecursively())
        if (!ok) return null
        metaFile(entry).delete()
        return target
    }

    fun deletePermanently(entry: TrashEntry): Boolean {
        val ok = entry.stored.deleteRecursively()
        metaFile(entry).delete()
        return ok
    }

    fun purgeExpired(): Int {
        var n = 0
        for (e in list()) if (daysLeft(e) <= 0 && deletePermanently(e)) n++
        return n
    }

    fun empty(): Int = list().count { deletePermanently(it) }

    private fun metaFile(entry: TrashEntry) = File(entry.stored.parentFile!!.parentFile, "meta/${entry.id}.txt")
}
