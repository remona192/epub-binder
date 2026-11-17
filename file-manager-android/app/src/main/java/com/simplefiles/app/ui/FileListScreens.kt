@file:OptIn(ExperimentalMaterial3Api::class, ExperimentalFoundationApi::class)

package com.simplefiles.app.ui

import androidx.compose.foundation.ExperimentalFoundationApi
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.RowScope
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.LazyRow
import androidx.compose.foundation.lazy.itemsIndexed
import androidx.compose.foundation.lazy.rememberLazyListState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.KeyboardActions
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.outlined.Close
import androidx.compose.material.icons.outlined.MoreVert
import androidx.compose.material.icons.outlined.Search
import androidx.compose.material3.Checkbox
import androidx.compose.material3.DropdownMenu
import androidx.compose.material3.DropdownMenuItem
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.FilterChip
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Scaffold
import androidx.compose.material3.SnackbarHost
import androidx.compose.material3.Text
import androidx.compose.material3.TextField
import androidx.compose.material3.TextFieldDefaults
import androidx.compose.material3.TopAppBar
import androidx.compose.material3.TopAppBarDefaults
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.produceState
import androidx.compose.runtime.remember
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.focus.FocusRequester
import androidx.compose.ui.focus.focusRequester
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalSoftwareKeyboardController
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import com.simplefiles.app.data.FileItem
import com.simplefiles.core.FileCategory
import com.simplefiles.core.SearchQuery
import com.simplefiles.core.TransferMode
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.delay
import kotlinx.coroutines.withContext
import java.io.File

/**
 * 폴더 / 카테고리 / 검색 결과가 함께 쓰는 화면 틀.
 * 길게 눌러 선택 → 하단 바(이동, 복사, 이름 변경, 삭제, 더보기)
 */
@Composable
fun FileListScaffold(
    vm: AppViewModel,
    title: String,
    items: List<FileItem>,
    loading: Boolean,
    pasteTarget: String? = null,
    emptyText: String = "항목이 없습니다",
    titleContent: (@Composable () -> Unit)? = null,
    topActions: @Composable RowScope.() -> Unit = {},
    header: (@Composable () -> Unit)? = null,
    subtitle: ((FileItem) -> String)? = null,
    highlight: ((FileItem) -> IntRange?)? = null,
    onDuplicatesHere: (() -> Unit)? = null,
) {
    val selecting = vm.selection.isNotEmpty()
    val selectedSet = vm.selection.toSet()
    val clip = vm.clipboard
    val listState = rememberLazyListState()

    Scaffold(
        containerColor = MaterialTheme.colorScheme.background,
        snackbarHost = { SnackbarHost(vm.snackbar) },
        topBar = {
            if (selecting) {
                TopAppBar(
                    colors = TopAppBarDefaults.topAppBarColors(containerColor = MaterialTheme.colorScheme.background),
                    navigationIcon = {
                        IconButton(onClick = { vm.selection.clear() }) { Icon(Icons.Outlined.Close, "선택 해제") }
                    },
                    title = { Text("${vm.selection.size}개 선택됨") },
                    actions = {
                        val all = items.isNotEmpty() && selectedSet.size == items.size
                        Row(
                            Modifier.clip(RoundedCornerShape(12.dp)).clickable {
                                if (all) vm.selection.clear() else vm.setSelection(items.map { it.path })
                            }.padding(end = 12.dp),
                            verticalAlignment = Alignment.CenterVertically,
                        ) {
                            Checkbox(checked = all, onCheckedChange = null, modifier = Modifier.padding(12.dp))
                            Text("전체")
                        }
                    },
                )
            } else {
                TopAppBar(
                    colors = TopAppBarDefaults.topAppBarColors(containerColor = MaterialTheme.colorScheme.background),
                    navigationIcon = {
                        IconButton(onClick = { vm.back() }) { Icon(Icons.AutoMirrored.Filled.ArrowBack, "뒤로") }
                    },
                    title = {
                        if (titleContent != null) titleContent()
                        else Text(title, maxLines = 1, overflow = TextOverflow.Ellipsis)
                    },
                    actions = topActions,
                )
            }
        },
        bottomBar = {
            when {
                selecting -> {
                    val paths = vm.selection.toList()
                    val single = paths.singleOrNull()?.let { File(it) }
                    SelectionBottomBar(
                        count = paths.size,
                        onMove = { vm.startClipboard(TransferMode.MOVE) },
                        onCopy = { vm.startClipboard(TransferMode.COPY) },
                        onRename = {
                            if (single != null) {
                                vm.renameTarget = FileItem.of(single)
                            } else {
                                vm.navigate(Screen.BatchRename(paths))
                            }
                        },
                        onDelete = { vm.requestDelete(paths) },
                        more = buildList {
                            add(MoreAction("공유") { vm.share(paths) })
                            if (single != null && single.isFile) {
                                add(MoreAction("다른 앱으로 열기") { vm.showChooser(single, single.extension.lowercase()) })
                            }
                            add(MoreAction("일괄 이름 변경") { vm.navigate(Screen.BatchRename(paths)) })
                            if (single != null) add(MoreAction("상세 정보") { vm.detailsTarget = FileItem.of(single, true) })
                            if (onDuplicatesHere != null) add(MoreAction("이 폴더에서 중복 찾기") { onDuplicatesHere() })
                        },
                    )
                }
                clip != null -> PasteBar(
                    mode = clip.mode,
                    count = clip.paths.size,
                    canPaste = pasteTarget != null,
                    onCancel = { vm.cancelClipboard() },
                    onPaste = { pasteTarget?.let { vm.pasteInto(it) } },
                )
            }
        },
    ) { padding ->
        Column(Modifier.padding(padding).fillMaxSize()) {
            header?.invoke()
            if (loading) LinearProgressIndicator(Modifier.fillMaxWidth().padding(horizontal = 24.dp, vertical = 4.dp))
            if (items.isEmpty()) {
                // 로딩 중에는 빈 목록을 그리지 않아야 뒤로 왔을 때 스크롤 위치가 유지된다
                if (!loading) EmptyState(emptyText)
            } else {
                LazyColumn(state = listState, contentPadding = PaddingValues(top = 4.dp, bottom = 24.dp)) {
                    itemsIndexed(items, key = { _, it -> it.path }) { i, item ->
                        FileRow(
                            item = item,
                            selectionMode = selecting,
                            selected = item.path in selectedSet,
                            onClick = { vm.onItemClick(item) },
                            onLongClick = { vm.toggleSelect(item.path) },
                            modifier = Modifier.cardItem(i, items.size),
                            subtitle = subtitle?.invoke(item) ?: subtitleOf(item),
                            highlight = highlight?.invoke(item),
                            showDivider = i != items.lastIndex,
                        )
                    }
                }
            }
        }
    }
}

// ======================= 폴더 =======================

@Composable
fun BrowserScreen(vm: AppViewModel, path: String) {
    val items by produceState<List<FileItem>?>(null, path, vm.refreshTick, vm.sortBy, vm.sortAscending, vm.showHidden) {
        value = withContext(Dispatchers.IO) { vm.listDir(path) }
    }
    var menu by remember { mutableStateOf(false) }
    var sortDialog by remember { mutableStateOf(false) }
    val root = vm.rootOf(path)
    val title = if (root != null && root.file.path == path) root.label else File(path).name

    FileListScaffold(
        vm = vm,
        title = title,
        items = items.orEmpty(),
        loading = items == null,
        pasteTarget = path,
        emptyText = "폴더가 비어 있습니다",
        onDuplicatesHere = { vm.navigate(Screen.Duplicates(path)) },
        topActions = {
            IconButton(onClick = { vm.navigate(Screen.Search) }) { Icon(Icons.Outlined.Search, "검색") }
            Box {
                IconButton(onClick = { menu = true }) { Icon(Icons.Outlined.MoreVert, "더보기") }
                DropdownMenu(expanded = menu, onDismissRequest = { menu = false }) {
                    DropdownMenuItem(text = { Text("새 폴더") }, onClick = { menu = false; vm.newFolderIn = path })
                    DropdownMenuItem(text = { Text("정렬") }, onClick = { menu = false; sortDialog = true })
                    DropdownMenuItem(
                        text = { Text(if (vm.showHidden) "숨김 파일 숨기기" else "숨김 파일 표시") },
                        onClick = { menu = false; vm.toggleShowHidden() },
                    )
                    DropdownMenuItem(
                        text = { Text("이 폴더에서 중복 찾기") },
                        onClick = { menu = false; vm.navigate(Screen.Duplicates(path)) },
                    )
                    DropdownMenuItem(
                        text = { Text("선택") },
                        onClick = { menu = false; items?.firstOrNull()?.let { vm.toggleSelect(it.path) } },
                    )
                }
            }
        },
        header = { Breadcrumb(vm, path) },
    )
    if (sortDialog) SortDialog(vm) { sortDialog = false }
}

@Composable
private fun Breadcrumb(vm: AppViewModel, path: String) {
    val root = vm.rootOf(path) ?: return
    val crumbs = remember(path, root) {
        val list = mutableListOf(root.label to root.file.path)
        var cur = root.file.path
        path.removePrefix(root.file.path).split('/').filter { it.isNotEmpty() }.forEach {
            cur = "$cur/$it"
            list += it to cur
        }
        list
    }
    val state = rememberLazyListState()
    LaunchedEffect(crumbs.size) { state.scrollToItem((crumbs.size - 1).coerceAtLeast(0)) }
    LazyRow(
        state = state,
        modifier = Modifier.fillMaxWidth().padding(horizontal = 16.dp, vertical = 4.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        itemsIndexed(crumbs) { i, (label, p) ->
            val last = i == crumbs.lastIndex
            Text(
                label,
                color = if (last) MaterialTheme.colorScheme.primary else MaterialTheme.colorScheme.onSurfaceVariant,
                fontWeight = if (last) FontWeight.SemiBold else FontWeight.Normal,
                style = MaterialTheme.typography.bodyMedium,
                modifier = Modifier.clip(RoundedCornerShape(8.dp)).clickable(enabled = !last) { vm.jumpTo(p) }
                    .padding(horizontal = 6.dp, vertical = 6.dp),
            )
            if (!last) Text("›", color = MaterialTheme.colorScheme.onSurfaceVariant)
        }
    }
}

// ======================= 카테고리 =======================

@Composable
fun CategoryScreen(vm: AppViewModel, category: FileCategory) {
    val entries by vm.index.entries.collectAsState()
    val ready by vm.index.ready.collectAsState()
    val items by produceState<List<FileItem>?>(null, entries, category) {
        value = withContext(Dispatchers.Default) {
            entries.asSequence()
                .filter { !it.item.isDir && FileCategory.of(it.item.name) == category }
                .map { it.item }
                .sortedByDescending { it.lastModified }
                .toList()
        }
    }
    FileListScaffold(
        vm = vm,
        title = category.label,
        items = items.orEmpty(),
        loading = items == null || !ready,
        emptyText = if (ready) "${category.label}이(가) 없습니다" else "저장공간을 읽는 중…",
        subtitle = { "${formatDate(it.lastModified)}  ·  ${formatSize(it.size)}  ·  ${vm.displayPath(File(it.path).parent ?: "")}" },
        topActions = {
            IconButton(onClick = { vm.navigate(Screen.Search) }) { Icon(Icons.Outlined.Search, "검색") }
        },
    )
}

// ======================= 검색 =======================

private enum class SearchFilter(val label: String) {
    ALL("전체"), FOLDERS("폴더"), IMAGES("이미지"), VIDEOS("동영상"), AUDIO("오디오"), DOCS("문서")
}

/** 휴대폰 저장공간 전체에서 파일명 검색. "내가"만 입력해도 "내가 잘못했다면"이 나온다. */
@Composable
fun SearchScreen(vm: AppViewModel) {
    var query by rememberSaveable { mutableStateOf("") }
    var filter by rememberSaveable { mutableStateOf(SearchFilter.ALL) }
    val entries by vm.index.entries.collectAsState()
    val scanning by vm.index.scanning.collectAsState()
    val focus = remember { FocusRequester() }
    val keyboard = LocalSoftwareKeyboardController.current
    val q = remember(query) { SearchQuery(query) }

    val results by produceState(emptyList<FileItem>(), q, entries, filter) {
        if (q.isEmpty) {
            value = emptyList()
            return@produceState
        }
        delay(120)
        value = withContext(Dispatchers.Default) {
            entries.asSequence()
                .filter { q.matches(it.key) }
                .filter { e ->
                    when (filter) {
                        SearchFilter.ALL -> true
                        SearchFilter.FOLDERS -> e.item.isDir
                        SearchFilter.IMAGES -> FileCategory.of(e.item.name) == FileCategory.IMAGES
                        SearchFilter.VIDEOS -> FileCategory.of(e.item.name) == FileCategory.VIDEOS
                        SearchFilter.AUDIO -> FileCategory.of(e.item.name) == FileCategory.AUDIO
                        SearchFilter.DOCS -> FileCategory.of(e.item.name) == FileCategory.DOCUMENTS
                    }
                }
                .sortedWith(compareBy({ q.rank(it.key) }, { !it.item.isDir }, { it.key }))
                .take(3000)
                .map { it.item }
                .toList()
        }
    }
    LaunchedEffect(Unit) { focus.requestFocus() }

    FileListScaffold(
        vm = vm,
        title = "검색",
        items = results,
        loading = false,
        emptyText = when {
            q.isEmpty -> "파일 이름의 일부만 입력해도 찾습니다\n(초성 검색 가능: ㄴㄱ → 내가…)"
            scanning -> "저장공간을 읽는 중… (${entries.size}개)"
            else -> "검색 결과가 없습니다"
        },
        titleContent = {
            TextField(
                value = query,
                onValueChange = { query = it },
                placeholder = { Text("내 휴대폰 전체에서 검색") },
                singleLine = true,
                keyboardOptions = KeyboardOptions(imeAction = ImeAction.Search),
                keyboardActions = KeyboardActions(onSearch = { keyboard?.hide() }),
                colors = TextFieldDefaults.colors(
                    focusedContainerColor = Color.Transparent,
                    unfocusedContainerColor = Color.Transparent,
                    focusedIndicatorColor = Color.Transparent,
                    unfocusedIndicatorColor = Color.Transparent,
                ),
                modifier = Modifier.fillMaxWidth().focusRequester(focus),
            )
        },
        topActions = {
            if (query.isNotEmpty()) {
                IconButton(onClick = { query = "" }) { Icon(Icons.Outlined.Close, "지우기") }
            }
        },
        header = {
            Column {
                LazyRow(
                    contentPadding = PaddingValues(horizontal = 16.dp),
                    horizontalArrangement = Arrangement.spacedBy(8.dp),
                ) {
                    itemsIndexed(SearchFilter.entries.toList()) { _, f ->
                        FilterChip(selected = filter == f, onClick = { filter = f }, label = { Text(f.label) })
                    }
                }
                if (!q.isEmpty) {
                    Text(
                        "결과 ${results.size}${if (results.size >= 3000) "+" else ""}개" + if (scanning) "  ·  색인 중 (${entries.size}개)" else "",
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                        modifier = Modifier.padding(start = 28.dp, top = 4.dp, bottom = 4.dp),
                    )
                }
            }
        },
        subtitle = { vm.displayPath(File(it.path).parent ?: "") + if (!it.isDir) "  ·  ${formatSize(it.size)}" else "" },
        highlight = { q.highlight(it.name) },
    )
}
