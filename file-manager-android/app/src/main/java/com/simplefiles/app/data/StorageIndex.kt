package com.simplefiles.app.data

import com.simplefiles.core.TextNorm
import com.simplefiles.core.TrashStore
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.ensureActive
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import java.io.File
import java.nio.file.DirectoryStream
import java.nio.file.Files
import java.nio.file.LinkOption
import java.nio.file.Path
import java.nio.file.attribute.BasicFileAttributes

data class IndexEntry(val item: FileItem, val key: String)

/**
 * 휴대폰 저장공간 전체(내장 + SD)의 파일 목록. 검색, 카테고리, 중복 검사에 쓴다.
 * 첫 색인 중에는 중간 결과를 계속 내보내 바로 검색할 수 있다.
 */
class StorageIndex(private val scope: CoroutineScope) {
    private val _entries = MutableStateFlow<List<IndexEntry>>(emptyList())
    val entries: StateFlow<List<IndexEntry>> = _entries.asStateFlow()

    private val _scanning = MutableStateFlow(false)
    val scanning: StateFlow<Boolean> = _scanning.asStateFlow()

    private val _ready = MutableStateFlow(false)
    /** 한 번이라도 전체 색인을 마쳤는지 */
    val ready: StateFlow<Boolean> = _ready.asStateFlow()

    private var job: Job? = null
    @Volatile private var generation = 0

    fun rebuild(roots: List<File>, showHidden: Boolean) {
        job?.cancel()
        val gen = ++generation
        job = scope.launch(Dispatchers.IO) {
            _scanning.value = true
            try {
                val list = ArrayList<IndexEntry>(if (_entries.value.isEmpty()) 20_000 else _entries.value.size + 1000)
                val publishPartial = !_ready.value
                var lastPublish = System.currentTimeMillis()
                val stack = ArrayDeque<Path>()
                roots.forEach { stack.addLast(it.toPath()) }
                while (stack.isNotEmpty()) {
                    ensureActive()
                    val dir = stack.removeAt(stack.lastIndex)
                    if (isSkipped(dir)) continue
                    val ds: DirectoryStream<Path> = try {
                        Files.newDirectoryStream(dir)
                    } catch (e: Exception) {
                        continue
                    }
                    try {
                        for (p in ds) {
                            val name = p.fileName?.toString() ?: continue
                            if (!showHidden && name.startsWith(".")) continue
                            if (name == TrashStore.DIR_NAME) continue
                            val attrs = try {
                                Files.readAttributes(p, BasicFileAttributes::class.java, LinkOption.NOFOLLOW_LINKS)
                            } catch (e: Exception) {
                                continue
                            }
                            if (attrs.isSymbolicLink) continue
                            val isDir = attrs.isDirectory
                            val item = FileItem(
                                p.toString(), name, isDir,
                                if (isDir) 0 else attrs.size(),
                                attrs.lastModifiedTime().toMillis(),
                            )
                            list.add(IndexEntry(item, TextNorm.key(name)))
                            if (isDir) stack.addLast(p)
                        }
                    } catch (e: Exception) {
                        // 읽기 실패한 폴더는 건너뛴다
                    } finally {
                        runCatching { ds.close() }
                    }
                    if (publishPartial) {
                        val now = System.currentTimeMillis()
                        if (now - lastPublish > 600) {
                            _entries.value = ArrayList(list)
                            lastPublish = now
                        }
                    }
                }
                _entries.value = list
                _ready.value = true
            } finally {
                if (gen == generation) _scanning.value = false
            }
        }
    }

    private fun isSkipped(dir: Path): Boolean {
        val s = dir.toString()
        return s.endsWith("/Android/data") || s.endsWith("/Android/obb")
    }
}
