@file:OptIn(ExperimentalMaterial3Api::class, ExperimentalFoundationApi::class)

package com.simplefiles.app.ui

import androidx.compose.foundation.ExperimentalFoundationApi
import androidx.compose.foundation.background
import androidx.compose.foundation.combinedClickable
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.itemsIndexed
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.outlined.Close
import androidx.compose.material.icons.outlined.DeleteForever
import androidx.compose.material.icons.outlined.Restore
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Scaffold
import androidx.compose.material3.SnackbarHost
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.TopAppBar
import androidx.compose.material3.TopAppBarDefaults
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateListOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import com.simplefiles.core.TrashEntry
import com.simplefiles.core.TrashStore
import java.io.File

@Composable
fun TrashScreen(vm: AppViewModel) {
    LaunchedEffect(Unit) { vm.loadTrash() }
    val entries = vm.trashEntries
    val selected = remember { mutableStateListOf<String>() }
    var confirm by remember { mutableStateOf<List<TrashEntry>?>(null) }
    val selecting = selected.isNotEmpty()
    fun chosen(): List<TrashEntry> = entries.orEmpty().filter { it.id in selected }

    Scaffold(
        containerColor = MaterialTheme.colorScheme.background,
        snackbarHost = { SnackbarHost(vm.snackbar) },
        topBar = {
            TopAppBar(
                colors = TopAppBarDefaults.topAppBarColors(containerColor = MaterialTheme.colorScheme.background),
                navigationIcon = {
                    if (selecting) IconButton(onClick = { selected.clear() }) { Icon(Icons.Outlined.Close, "선택 해제") }
                    else IconButton(onClick = { vm.back() }) { Icon(Icons.AutoMirrored.Filled.ArrowBack, "뒤로") }
                },
                title = { Text(if (selecting) "${selected.size}개 선택됨" else "휴지통") },
                actions = {
                    if (selecting) {
                        TextButton(onClick = {
                            val all = entries.orEmpty().map { it.id }
                            if (selected.size == all.size) selected.clear() else { selected.clear(); selected.addAll(all) }
                        }) { Text("전체") }
                    } else if (!entries.isNullOrEmpty()) {
                        TextButton(onClick = { confirm = entries }) { Text("비우기") }
                    }
                },
            )
        },
        bottomBar = {
            if (selecting) {
                BottomBarSurface {
                    BottomAction(Icons.Outlined.Restore, "복원") {
                        vm.restoreFromTrash(chosen())
                        selected.clear()
                    }
                    BottomAction(Icons.Outlined.DeleteForever, "영구 삭제") { confirm = chosen() }
                }
            }
        },
    ) { padding ->
        Column(Modifier.padding(padding).fillMaxSize()) {
            Text(
                "삭제한 항목은 ${TrashStore.RETENTION_DAYS}일 동안 보관된 뒤 영구 삭제됩니다.",
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
                modifier = Modifier.padding(horizontal = 28.dp, vertical = 8.dp),
            )
            when {
                entries == null -> LinearProgressIndicator(Modifier.fillMaxWidth().padding(24.dp))
                entries.isEmpty() -> EmptyState("휴지통이 비어 있습니다")
                else -> LazyColumn(contentPadding = PaddingValues(bottom = 24.dp)) {
                    itemsIndexed(entries, key = { _, e -> e.id }) { i, e ->
                        val isSel = e.id in selected
                        Column(Modifier.cardItem(i, entries.size)) {
                            Row(
                                Modifier
                                    .fillMaxWidth()
                                    .combinedClickable(
                                        onClick = { if (selecting) toggle(selected, e.id) else toggle(selected, e.id) },
                                        onLongClick = { toggle(selected, e.id) },
                                    )
                                    .background(if (isSel) MaterialTheme.colorScheme.primary.copy(alpha = 0.08f) else Color.Transparent)
                                    .padding(horizontal = 16.dp, vertical = 10.dp),
                                verticalAlignment = Alignment.CenterVertically,
                            ) {
                                SelectMark(isSel)
                                Spacer(Modifier.width(12.dp))
                                FileIcon(e.name, e.stored.path, e.isDirectory)
                                Spacer(Modifier.width(12.dp))
                                Column(Modifier.weight(1f)) {
                                    Text(e.name, maxLines = 2, overflow = TextOverflow.Ellipsis)
                                    Text(
                                        vm.displayPath(File(e.originalPath).parent ?: "") + "  ·  ${vm.trash.daysLeft(e)}일 남음",
                                        style = MaterialTheme.typography.bodySmall,
                                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                                        maxLines = 1,
                                        overflow = TextOverflow.Ellipsis,
                                    )
                                }
                            }
                            if (i != entries.lastIndex) {
                                HorizontalDivider(Modifier.padding(start = 110.dp, end = 16.dp), color = MaterialTheme.colorScheme.outlineVariant)
                            }
                        }
                    }
                }
            }
        }
    }

    confirm?.let { list ->
        AlertDialog(
            onDismissRequest = { confirm = null },
            title = { Text("영구 삭제할까요?") },
            text = { Text("${list.size}개 항목을 영구 삭제합니다. 되돌릴 수 없습니다.") },
            confirmButton = {
                TextButton(onClick = {
                    vm.deleteFromTrash(list)
                    selected.clear()
                    confirm = null
                }) { Text("삭제", color = MaterialTheme.colorScheme.error) }
            },
            dismissButton = { TextButton(onClick = { confirm = null }) { Text("취소") } },
        )
    }
}

private fun toggle(list: MutableList<String>, id: String) {
    if (!list.remove(id)) list.add(id)
}
