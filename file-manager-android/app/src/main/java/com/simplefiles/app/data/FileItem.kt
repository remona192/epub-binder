package com.simplefiles.app.data

import com.simplefiles.core.NameUtil
import com.simplefiles.core.NaturalOrder
import java.io.File

data class FileItem(
    val path: String,
    val name: String,
    val isDir: Boolean,
    val size: Long,
    val lastModified: Long,
    /** 폴더의 항목 수 (모르면 -1) */
    val childCount: Int = -1,
) {
    val file: File get() = File(path)
    val ext: String get() = NameUtil.ext(name)

    companion object {
        fun of(f: File, countChildren: Boolean = false, showHidden: Boolean = false): FileItem {
            val dir = f.isDirectory
            val count = if (countChildren && dir) {
                f.list()?.count { showHidden || !it.startsWith(".") } ?: 0
            } else -1
            return FileItem(f.path, f.name, dir, if (dir) 0 else f.length(), f.lastModified(), count)
        }
    }
}

enum class SortBy(val label: String) { NAME("이름"), DATE("수정 날짜"), SIZE("크기"), TYPE("유형") }

fun fileComparator(sortBy: SortBy, ascending: Boolean): Comparator<FileItem> {
    val byName = Comparator<FileItem> { a, b -> NaturalOrder.compare(a.name, b.name) }
    val base: Comparator<FileItem> = when (sortBy) {
        SortBy.NAME -> byName
        SortBy.DATE -> compareBy<FileItem> { it.lastModified }.then(byName)
        SortBy.SIZE -> compareBy<FileItem> { if (it.isDir) it.childCount.toLong() else it.size }.then(byName)
        SortBy.TYPE -> compareBy<FileItem> { it.ext }.then(byName)
    }
    val ordered = if (ascending) base else base.reversed()
    // 폴더는 항상 위
    return compareBy<FileItem> { !it.isDir }.then(ordered)
}
