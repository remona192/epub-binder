package com.simplefiles.app.ui

import android.app.Application
import android.content.ComponentName
import androidx.compose.material3.SnackbarDuration
import androidx.compose.material3.SnackbarHostState
import androidx.compose.material3.SnackbarResult
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableFloatStateOf
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateListOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import androidx.compose.ui.graphics.ImageBitmap
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import com.simplefiles.app.data.AppChoice
import com.simplefiles.app.data.FileItem
import com.simplefiles.app.data.FileOpener
import com.simplefiles.app.data.Prefs
import com.simplefiles.app.data.SortBy
import com.simplefiles.app.data.Storage
import com.simplefiles.app.data.StorageIndex
import com.simplefiles.app.data.StorageRoot
import com.simplefiles.app.data.fileComparator
import com.simplefiles.core.BatchRenamer
import com.simplefiles.core.ConflictChoice
import com.simplefiles.core.ConflictDecision
import com.simplefiles.core.DupCandidate
import com.simplefiles.core.DupGroup
import com.simplefiles.core.DupOptions
import com.simplefiles.core.DuplicateFinder
import com.simplefiles.core.FileCategory
import com.simplefiles.core.FileTransfer
import com.simplefiles.core.NameUtil
import com.simplefiles.core.TransferMode
import com.simplefiles.core.TrashEntry
import com.simplefiles.core.TrashStore
import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.isActive
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import java.io.File

sealed interface Screen {
    val key: String

    data object Home : Screen { override val key = "home" }
    data class Browser(val path: String) : Screen { override val key get() = "browser:$path" }
    data class Category(val category: FileCategory) : Screen { override val key get() = "category:${category.name}" }
    data object Search : Screen { override val key = "search" }
    data class BatchRename(val paths: List<String>) : Screen { override val key get() = "rename:${paths.hashCode()}" }
    data class Duplicates(val scope: String?) : Screen { override val key get() = "dup:$scope" }
    data object Trash : Screen { override val key = "trash" }
    data object Settings : Screen { override val key = "settings" }
}

data class Clipboard(val paths: List<String>, val mode: TransferMode)
data class ProgressUi(val title: String, val done: Int, val total: Int, val current: String)
data class ConflictUi(val name: String, val folder: String, val isDir: Boolean, val result: CompletableDeferred<ConflictDecision>)
data class ChooserUi(val file: File?, val ext: String, val apps: List<AppChoice>, val current: ComponentName?)
data class DefaultAppUi(val ext: String, val component: ComponentName, val label: String, val icon: ImageBitmap?)

class AppViewModel(app: Application) : AndroidViewModel(app) {
    private val prefs = Prefs(app)
    val opener = FileOpener(app, prefs)
    val index = StorageIndex(viewModelScope)
    val trash = TrashStore(roots = { roots.map { it.file } })
    val snackbar = SnackbarHostState()

    var hasPermission by mutableStateOf(false)
        private set
    var roots by mutableStateOf<List<StorageRoot>>(emptyList())
        private set

    val backStack = mutableStateListOf<Screen>(Screen.Home)
    val current: Screen get() = backStack.last()

    /** 선택된 경로들 */
    val selection = mutableStateListOf<String>()

    /** 파일 작업 후 목록을 다시 읽기 위한 신호 */
    var refreshTick by mutableIntStateOf(0)
        private set

    // ---- 설정 ----
    var sortBy by mutableStateOf(prefs.sortBy)
        private set
    var sortAscending by mutableStateOf(prefs.sortAscending)
        private set
    var showHidden by mutableStateOf(prefs.showHidden)
        private set
    var useTrash by mutableStateOf(prefs.useTrash)
        private set

    // ---- 복사/이동 대기 ----
    var clipboard by mutableStateOf<Clipboard?>(null)
        private set

    // ---- 대화상자 ----
    var progress by mutableStateOf<ProgressUi?>(null)
        private set
    var conflict by mutableStateOf<ConflictUi?>(null)
        private set
    var confirmDelete by mutableStateOf<List<String>?>(null)
    var renameTarget by mutableStateOf<FileItem?>(null)
    var newFolderIn by mutableStateOf<String?>(null)
    var detailsTarget by mutableStateOf<FileItem?>(null)
    var chooser by mutableStateOf<ChooserUi?>(null)
        private set
    var defaultAppsVersion by mutableIntStateOf(0)
        private set

    private var opJob: Job? = null
    @Volatile private var cancelRequested = false

    // ---- 중복 검사 ----
    var dupOptions by mutableStateOf(DupOptions())
    var dupRunning by mutableStateOf(false)
        private set
    var dupProgress by mutableFloatStateOf(0f)
        private set
    var dupGroups by mutableStateOf<List<DupGroup>?>(null)
        private set
    val dupSelected = mutableStateListOf<String>()
    private var dupJob: Job? = null

    // ---- 휴지통 ----
    var trashEntries by mutableStateOf<List<TrashEntry>?>(null)
        private set

    // ================= 권한 / 초기화 =================

    fun refreshPermission() {
        val granted = Storage.hasAllFilesAccess(getApplication())
        val first = granted && !hasPermission
        hasPermission = granted
        if (first) {
            roots = Storage.roots(getApplication())
            rebuildIndex()
            viewModelScope.launch(Dispatchers.IO) { runCatching { trash.purgeExpired() } }
        }
    }

    fun rebuildIndex() = index.rebuild(roots.map { it.file }, showHidden)

    // ================= 이동(내비게이션) =================

    fun navigate(screen: Screen) {
        selection.clear()
        backStack.add(screen)
    }

    /** @return 처리했으면 true */
    fun back(): Boolean {
        if (selection.isNotEmpty()) {
            selection.clear()
            return true
        }
        if (backStack.size > 1) {
            backStack.removeAt(backStack.lastIndex)
            return true
        }
        return false
    }

    fun goHome() {
        selection.clear()
        while (backStack.size > 1) backStack.removeAt(backStack.lastIndex)
    }

    /** 경로 표시줄에서 상위 폴더를 눌렀을 때 */
    fun jumpTo(path: String) {
        selection.clear()
        val idx = backStack.indexOfLast { it is Screen.Browser && it.path == path }
        if (idx >= 0) {
            while (backStack.size > idx + 1) backStack.removeAt(backStack.lastIndex)
        } else {
            backStack.add(Screen.Browser(path))
        }
    }

    fun rootOf(path: String): StorageRoot? =
        roots.filter { NameUtil.isInside(File(path), it.file) }.maxByOrNull { it.file.path.length }

    /** "내장 메모리/Download/책" 같은 표시용 경로 */
    fun displayPath(path: String): String {
        val root = rootOf(path) ?: return path
        val rest = path.removePrefix(root.file.path).trim('/')
        return if (rest.isEmpty()) root.label else root.label + "/" + rest
    }

    // ================= 목록 =================

    fun listDir(path: String): List<FileItem> {
        val files = File(path).listFiles() ?: return emptyList()
        return files
            .filter { showHidden || !it.name.startsWith(".") }
            .filter { it.name != TrashStore.DIR_NAME }
            .map { FileItem.of(it, countChildren = true, showHidden = showHidden) }
            .sortedWith(fileComparator(sortBy, sortAscending))
    }

    fun setSort(by: SortBy, ascending: Boolean) {
        sortBy = by
        sortAscending = ascending
        prefs.sortBy = by
        prefs.sortAscending = ascending
    }

    fun toggleShowHidden() {
        showHidden = !showHidden
        prefs.showHidden = showHidden
        rebuildIndex()
    }

    fun toggleUseTrash() {
        useTrash = !useTrash
        prefs.useTrash = useTrash
    }

    // ================= 선택 =================

    fun toggleSelect(path: String) {
        if (!selection.remove(path)) selection.add(path)
    }

    fun setSelection(paths: List<String>) {
        selection.clear()
        selection.addAll(paths)
    }

    fun onItemClick(item: FileItem) {
        when {
            selection.isNotEmpty() -> toggleSelect(item.path)
            item.isDir -> navigate(Screen.Browser(item.path))
            else -> openFile(item.file)
        }
    }

    // ================= 열기 =================

    /** 기본 앱이 정해져 있으면 바로, 아니면 앱 고르기 */
    fun openFile(file: File) {
        val ext = NameUtil.ext(file.name)
        val def = opener.defaultFor(ext)
        if (def != null && opener.launch(file, def)) return
        showChooser(file, ext)
    }

    /** 다른 앱으로 열기 / 기본 앱 변경 */
    fun showChooser(file: File?, ext: String) {
        viewModelScope.launch {
            val apps = withContext(Dispatchers.IO) { opener.handlers(ext, file) }
            if (apps.isEmpty()) {
                if (file != null && opener.launch(file, null)) return@launch
                message("이 파일을 열 수 있는 앱이 없습니다")
                return@launch
            }
            chooser = ChooserUi(file, ext, apps, prefs.defaultApp(ext))
        }
    }

    fun chooseApp(choice: AppChoice, always: Boolean) {
        val c = chooser ?: return
        chooser = null
        if (always) {
            prefs.setDefaultApp(c.ext, choice.component)
            defaultAppsVersion++
            message("${extLabel(c.ext)} 파일은 이제 '${choice.label}'(으)로 열립니다")
        }
        if (c.file != null && !opener.launch(c.file, choice.component)) message("앱을 실행할 수 없습니다")
    }

    fun dismissChooser() {
        chooser = null
    }

    fun clearDefaultApp(ext: String) {
        prefs.setDefaultApp(ext, null)
        defaultAppsVersion++
    }

    fun defaultApps(): List<DefaultAppUi> =
        prefs.allDefaultApps().entries.sortedBy { it.key }.map { (ext, cn) ->
            DefaultAppUi(ext, cn, opener.appLabel(cn), opener.appIcon(cn))
        }

    fun extLabel(ext: String) = if (ext.isEmpty()) "확장자 없는" else ".$ext"

    fun share(paths: List<String>) {
        if (!opener.share(paths.map { File(it) }.filter { it.isFile })) message("공유할 파일이 없습니다 (폴더는 공유할 수 없습니다)")
    }

    // ================= 복사 / 이동 =================

    fun startClipboard(mode: TransferMode) {
        if (selection.isEmpty()) return
        clipboard = Clipboard(selection.toList(), mode)
        selection.clear()
    }

    fun cancelClipboard() {
        clipboard = null
    }

    fun pasteInto(dirPath: String) {
        val clip = clipboard ?: return
        clipboard = null
        val title = if (clip.mode == TransferMode.COPY) "복사 중" else "이동 중"
        runOp(title) { report, cancelled ->
            val t = FileTransfer(
                onConflict = { src, target -> askConflict(src, target) },
                onProgress = { p -> report(p.done, p.total, p.currentName) },
                isCancelled = cancelled,
            )
            val r = t.run(clip.paths.map { File(it) }, File(dirPath), clip.mode)
            val verb = if (clip.mode == TransferMode.COPY) "복사" else "이동"
            buildString {
                append(if (r.cancelled) "취소됨: " else "")
                append("${r.succeeded}개 $verb")
                if (r.skipped > 0) append(", ${r.skipped}개 건너뜀")
                if (r.failures.isNotEmpty()) append(", ${r.failures.size}개 실패 (${r.failures.first().second})")
            }
        }
    }

    private suspend fun askConflict(src: File, target: File): ConflictDecision {
        val d = CompletableDeferred<ConflictDecision>()
        withContext(Dispatchers.Main) {
            conflict = ConflictUi(src.name, target.parentFile?.name ?: "", src.isDirectory, d)
        }
        val result = d.await()
        withContext(Dispatchers.Main) { conflict = null }
        return result
    }

    fun answerConflict(choice: ConflictChoice, applyToAll: Boolean) {
        conflict?.result?.complete(ConflictDecision(choice, applyToAll))
    }

    fun cancelOperation() {
        cancelRequested = true
        conflict?.result?.complete(ConflictDecision(ConflictChoice.SKIP, true))
    }

    // ================= 삭제 / 이름 / 새 폴더 =================

    fun requestDelete(paths: List<String>) {
        if (paths.isNotEmpty()) confirmDelete = paths
    }

    fun confirmDeleteNow() {
        val paths = confirmDelete ?: return
        confirmDelete = null
        selection.clear()
        val toTrash = useTrash
        runOp(if (toTrash) "휴지통으로 이동 중" else "삭제 중") { report, cancelled ->
            var ok = 0
            var fail = 0
            paths.forEachIndexed { i, p ->
                if (cancelled()) return@forEachIndexed
                val f = File(p)
                report(i, paths.size, f.name)
                val done = if (toTrash && !trash.isTrashPath(f)) trash.moveToTrash(f) else f.deleteRecursively()
                if (done) ok++ else fail++
            }
            withContext(Dispatchers.Main) { dupSelected.removeAll(paths.toSet()) }
            val verb = if (toTrash) "휴지통으로 이동" else "삭제"
            "${ok}개 $verb" + if (fail > 0) ", ${fail}개 실패" else ""
        }
    }

    fun rename(item: FileItem, newName: String): String? {
        NameUtil.invalidReason(newName)?.let { return it }
        if (newName == item.name) return null
        val target = File(item.file.parentFile, newName)
        val caseOnly = newName.equals(item.name, ignoreCase = true)
        if (!caseOnly && target.exists()) return "같은 이름의 항목이 이미 있습니다"
        val res = BatchRenamer.execute(listOf(item.file to newName))
        if (res.failures.isNotEmpty()) return "이름을 바꿀 수 없습니다"
        afterChange()
        return null
    }

    fun createFolder(parent: String, name: String): String? {
        NameUtil.invalidReason(name)?.let { return it }
        val f = File(parent, name)
        if (f.exists()) return "같은 이름의 항목이 이미 있습니다"
        if (!f.mkdirs()) return "폴더를 만들 수 없습니다"
        afterChange()
        return null
    }

    // ================= 일괄 이름 변경 =================

    fun applyBatchRename(changes: List<Pair<File, String>>) {
        viewModelScope.launch {
            val res = withContext(Dispatchers.IO) { BatchRenamer.execute(changes) }
            afterChange()
            if (current is Screen.BatchRename) back()
            val msg = "${res.applied.size}개 이름을 바꿨습니다" +
                if (res.failures.isNotEmpty()) " (${res.failures.size}개 실패)" else ""
            if (res.applied.isEmpty()) {
                message(msg)
                return@launch
            }
            val r = snackbar.showSnackbar(msg, actionLabel = "실행 취소", duration = SnackbarDuration.Long)
            if (r == SnackbarResult.ActionPerformed) {
                val u = withContext(Dispatchers.IO) { BatchRenamer.undo(res.applied) }
                afterChange()
                message("${u.applied.size}개를 원래 이름으로 되돌렸습니다")
            }
        }
    }

    // ================= 중복 검사 =================

    fun runDuplicates(scope: String?) {
        dupJob?.cancel()
        dupRunning = true
        dupProgress = 0f
        dupGroups = null
        dupSelected.clear()
        val options = dupOptions
        dupJob = viewModelScope.launch {
            index.ready.first { it }
            val entries = index.entries.value
            val prefix = scope?.trimEnd('/')?.plus("/")
            val groups = withContext(Dispatchers.Default) {
                val cands = entries.asSequence()
                    .filter { !it.item.isDir && (prefix == null || it.item.path.startsWith(prefix)) }
                    .map { DupCandidate(it.item.path, it.item.name, it.item.size, it.item.lastModified) }
                    .toList()
                DuplicateFinder.find(cands, options, { p -> dupProgress = p }, { !isActive })
            }
            dupGroups = groups
            dupRunning = false
        }
    }

    fun cancelDuplicates() {
        dupJob?.cancel()
        dupRunning = false
    }

    /** 그룹마다 가장 최근 파일 하나만 남기고 나머지를 선택 */
    fun dupSelectAllButNewest() {
        dupSelected.clear()
        dupGroups?.forEach { g -> g.members.drop(1).forEach { dupSelected.add(it.file.path) } }
    }

    fun toggleDup(path: String) {
        if (!dupSelected.remove(path)) dupSelected.add(path)
    }

    // ================= 휴지통 =================

    fun loadTrash() {
        viewModelScope.launch {
            trashEntries = withContext(Dispatchers.IO) { trash.list() }
        }
    }

    fun restoreFromTrash(entries: List<TrashEntry>) {
        runOp("복원 중") { report, _ ->
            var ok = 0
            entries.forEachIndexed { i, e ->
                report(i, entries.size, e.name)
                if (trash.restore(e) != null) ok++
            }
            "${ok}개 복원" + if (ok < entries.size) ", ${entries.size - ok}개 실패" else ""
        }
    }

    fun deleteFromTrash(entries: List<TrashEntry>) {
        runOp("영구 삭제 중") { report, _ ->
            entries.forEachIndexed { i, e ->
                report(i, entries.size, e.name)
                trash.deletePermanently(e)
            }
            "${entries.size}개 영구 삭제"
        }
    }

    // ================= 공통 =================

    fun message(text: String) {
        viewModelScope.launch { snackbar.showSnackbar(text) }
    }

    private fun afterChange() {
        refreshTick++
        rebuildIndex()
        if (trashEntries != null) loadTrash()
        dupGroups?.let { gs ->
            dupGroups = gs.map { g -> DupGroup(g.members.filter { File(it.file.path).exists() }) }.filter { it.members.size >= 2 }
        }
    }

    /**
     * 진행률 대화상자와 함께 백그라운드 작업 실행.
     * [block]은 (완료, 전체, 이름) 보고 함수와 취소 확인 함수를 받고, 끝나면 보여줄 메시지를 돌려준다.
     */
    private fun runOp(
        title: String,
        block: suspend (report: (Int, Int, String) -> Unit, cancelled: () -> Boolean) -> String?,
    ) {
        if (opJob?.isActive == true) {
            message("다른 작업이 진행 중입니다")
            return
        }
        cancelRequested = false
        progress = ProgressUi(title, 0, 0, "")
        opJob = viewModelScope.launch {
            var last = 0L
            val msg = try {
                withContext(Dispatchers.IO) {
                    block(
                        { d, t, n ->
                            val now = System.currentTimeMillis()
                            if (now - last > 80 || d >= t) {
                                last = now
                                progress = ProgressUi(title, d, t, n)
                            }
                        },
                        { cancelRequested },
                    )
                }
            } catch (e: Exception) {
                "오류: ${e.message}"
            }
            progress = null
            conflict = null
            afterChange()
            msg?.let { message(it) }
        }
    }
}
