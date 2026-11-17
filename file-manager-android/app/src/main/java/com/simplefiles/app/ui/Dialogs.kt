package com.simplefiles.app.ui

import androidx.compose.foundation.Image
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.outlined.Apps
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Checkbox
import androidx.compose.material3.Icon
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.RadioButton
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.produceState
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.focus.FocusRequester
import androidx.compose.ui.focus.focusRequester
import androidx.compose.ui.text.TextRange
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.TextFieldValue
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.window.DialogProperties
import com.simplefiles.app.data.AppChoice
import com.simplefiles.app.data.SortBy
import com.simplefiles.core.ConflictChoice
import com.simplefiles.core.NameUtil
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import java.io.File

/** 모든 화면 위에 뜨는 대화상자들 */
@Composable
fun GlobalDialogs(vm: AppViewModel) {
    vm.progress?.let { p ->
        AlertDialog(
            onDismissRequest = {},
            properties = DialogProperties(dismissOnBackPress = false, dismissOnClickOutside = false),
            title = { Text(p.title) },
            text = {
                Column {
                    Text(
                        if (p.total > 0) "${p.done} / ${p.total}" else "준비 중…",
                        style = MaterialTheme.typography.bodyMedium,
                    )
                    Spacer(Modifier.height(4.dp))
                    Text(p.current, maxLines = 1, overflow = TextOverflow.Ellipsis, style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant)
                    Spacer(Modifier.height(12.dp))
                    if (p.total > 0) {
                        LinearProgressIndicator(progress = { p.done.toFloat() / p.total }, modifier = Modifier.fillMaxWidth())
                    } else {
                        LinearProgressIndicator(Modifier.fillMaxWidth())
                    }
                }
            },
            confirmButton = { TextButton(onClick = { vm.cancelOperation() }) { Text("취소") } },
        )
    }

    vm.conflict?.let { c -> ConflictDialog(vm, c) }

    vm.confirmDelete?.let { paths ->
        val toTrash = vm.useTrash
        AlertDialog(
            onDismissRequest = { vm.confirmDelete = null },
            title = { Text(if (toTrash) "휴지통으로 이동할까요?" else "영구 삭제할까요?") },
            text = {
                val name = File(paths.first()).name
                Text(
                    (if (paths.size == 1) "'$name'" else "'$name' 외 ${paths.size - 1}개 항목") +
                        if (toTrash) "을(를) 휴지통으로 이동합니다. 30일 동안 복원할 수 있습니다." else "을(를) 삭제합니다. 되돌릴 수 없습니다.",
                )
            },
            confirmButton = {
                TextButton(onClick = { vm.confirmDeleteNow() }) {
                    Text(if (toTrash) "휴지통으로 이동" else "삭제", color = MaterialTheme.colorScheme.error)
                }
            },
            dismissButton = { TextButton(onClick = { vm.confirmDelete = null }) { Text("취소") } },
        )
    }

    vm.renameTarget?.let { item ->
        NameDialog(
            title = "이름 변경",
            initial = item.name,
            selectBaseOnly = !item.isDir,
            confirmLabel = "변경",
            onDismiss = { vm.renameTarget = null },
        ) { newName ->
            val err = vm.rename(item, newName.trim())
            if (err == null) {
                vm.renameTarget = null
                vm.selection.clear()
            }
            err
        }
    }

    vm.newFolderIn?.let { parent ->
        NameDialog(
            title = "새 폴더",
            initial = "",
            selectBaseOnly = false,
            confirmLabel = "만들기",
            onDismiss = { vm.newFolderIn = null },
        ) { name ->
            val err = vm.createFolder(parent, name.trim())
            if (err == null) vm.newFolderIn = null
            err
        }
    }

    vm.detailsTarget?.let { item ->
        val dirInfo by produceState<Pair<Long, Int>?>(null, item.path) {
            if (item.isDir) {
                value = withContext(Dispatchers.IO) {
                    var size = 0L
                    var count = 0
                    item.file.walkTopDown().forEach { if (it.isFile) { size += it.length(); count++ } }
                    size to count
                }
            }
        }
        AlertDialog(
            onDismissRequest = { vm.detailsTarget = null },
            title = { Text("상세 정보") },
            text = {
                Column(verticalArrangement = Arrangement.spacedBy(10.dp)) {
                    DetailLine("이름", item.name)
                    DetailLine("위치", vm.displayPath(item.file.parent ?: ""))
                    DetailLine("실제 경로", item.path)
                    if (item.isDir) {
                        DetailLine("크기", dirInfo?.let { "${formatSize(it.first)} (파일 ${it.second}개)" } ?: "계산 중…")
                    } else {
                        DetailLine("크기", "${formatSize(item.size)} (${"%,d".format(item.size)} 바이트)")
                        DetailLine("형식", vm.opener.mimeOf(item.name))
                    }
                    DetailLine("수정한 날짜", formatDate(item.lastModified))
                }
            },
            confirmButton = { TextButton(onClick = { vm.detailsTarget = null }) { Text("확인") } },
        )
    }

    vm.chooser?.let { c -> AppChooserDialog(vm, c) }
}

@Composable
private fun DetailLine(label: String, value: String) {
    Column {
        Text(label, style = MaterialTheme.typography.labelMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
        Text(value, style = MaterialTheme.typography.bodyMedium)
    }
}

@Composable
private fun ConflictDialog(vm: AppViewModel, c: ConflictUi) {
    var applyAll by remember(c) { mutableStateOf(false) }
    AlertDialog(
        onDismissRequest = {},
        properties = DialogProperties(dismissOnBackPress = false, dismissOnClickOutside = false),
        title = { Text(if (c.isDir) "같은 이름의 폴더가 있습니다" else "같은 이름의 파일이 있습니다") },
        text = {
            Column {
                Text("'${c.name}'이(가) '${c.folder}' 폴더에 이미 있습니다.")
                Spacer(Modifier.height(12.dp))
                Row(
                    Modifier.clip(RoundedCornerShape(8.dp)).clickable { applyAll = !applyAll },
                    verticalAlignment = Alignment.CenterVertically,
                ) {
                    Checkbox(checked = applyAll, onCheckedChange = { applyAll = it })
                    Text("남은 항목에 모두 적용")
                }
                Spacer(Modifier.height(8.dp))
                val opts = listOf(
                    ConflictChoice.SKIP to "건너뛰기",
                    ConflictChoice.KEEP_BOTH to "이름 변경 (둘 다 유지)",
                    ConflictChoice.REPLACE to if (c.isDir) "바꾸기 (폴더 합치기)" else "바꾸기 (덮어쓰기)",
                )
                opts.forEach { (choice, label) ->
                    OutlinedButton(
                        onClick = { vm.answerConflict(choice, applyAll) },
                        modifier = Modifier.fillMaxWidth().padding(vertical = 3.dp),
                    ) { Text(label) }
                }
            }
        },
        confirmButton = { TextButton(onClick = { vm.cancelOperation() }) { Text("작업 취소") } },
    )
}

@Composable
private fun NameDialog(
    title: String,
    initial: String,
    selectBaseOnly: Boolean,
    confirmLabel: String,
    onDismiss: () -> Unit,
    onConfirm: (String) -> String?,
) {
    val baseLen = if (selectBaseOnly) NameUtil.splitExt(initial).first.length else initial.length
    var value by remember { mutableStateOf(TextFieldValue(initial, TextRange(0, baseLen))) }
    var error by remember { mutableStateOf<String?>(null) }
    val focus = remember { FocusRequester() }
    LaunchedEffect(Unit) { focus.requestFocus() }
    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text(title) },
        text = {
            OutlinedTextField(
                value = value,
                onValueChange = {
                    value = it
                    error = null
                },
                singleLine = true,
                isError = error != null,
                supportingText = { error?.let { Text(it) } },
                modifier = Modifier.fillMaxWidth().focusRequester(focus),
            )
        },
        confirmButton = {
            TextButton(onClick = { error = onConfirm(value.text) }, enabled = value.text.isNotBlank()) { Text(confirmLabel) }
        },
        dismissButton = { TextButton(onClick = onDismiss) { Text("취소") } },
    )
}

/**
 * 앱 고르기. "항상"을 누르면 그 확장자는 다음부터 묻지 않고 바로 연다.
 * 바꾸려면 파일 길게 누르기 → 더보기 → 다른 앱으로 열기, 또는 설정 → 기본 앱.
 */
@Composable
private fun AppChooserDialog(vm: AppViewModel, c: ChooserUi) {
    var selected by remember(c) { mutableStateOf(c.apps.firstOrNull { it.component == c.current } ?: c.apps.firstOrNull()) }
    AlertDialog(
        onDismissRequest = { vm.dismissChooser() },
        title = { Text(if (c.file != null) "다음으로 열기" else "${vm.extLabel(c.ext)} 파일의 기본 앱") },
        text = {
            Column {
                c.file?.let {
                    Text(it.name, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant,
                        maxLines = 1, overflow = TextOverflow.Ellipsis)
                    Spacer(Modifier.height(8.dp))
                }
                LazyColumn(Modifier.heightIn(max = 360.dp)) {
                    items(c.apps, key = { it.component.flattenToString() }) { app ->
                        AppRow(app, app == selected, app.component == c.current) { selected = app }
                    }
                }
                Spacer(Modifier.height(8.dp))
                Text(
                    "'항상'을 고르면 ${vm.extLabel(c.ext)} 파일은 다음부터 바로 이 앱으로 열립니다. " +
                        "설정 › 기본 앱에서 언제든 바꿀 수 있습니다.",
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
        },
        confirmButton = {
            Row {
                if (c.file != null) {
                    TextButton(enabled = selected != null, onClick = { selected?.let { vm.chooseApp(it, always = false) } }) {
                        Text("한 번만")
                    }
                }
                TextButton(enabled = selected != null, onClick = { selected?.let { vm.chooseApp(it, always = true) } }) {
                    Text("항상", fontWeight = FontWeight.SemiBold)
                }
            }
        },
        dismissButton = { TextButton(onClick = { vm.dismissChooser() }) { Text("취소") } },
    )
}

@Composable
private fun AppRow(app: AppChoice, selected: Boolean, isCurrent: Boolean, onClick: () -> Unit) {
    Row(
        Modifier
            .fillMaxWidth()
            .clip(RoundedCornerShape(12.dp))
            .background(if (selected) MaterialTheme.colorScheme.primary.copy(alpha = 0.10f) else MaterialTheme.colorScheme.surfaceContainerHigh)
            .clickable(onClick = onClick)
            .padding(horizontal = 10.dp, vertical = 8.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Box(Modifier.size(40.dp), contentAlignment = Alignment.Center) {
            if (app.icon != null) Image(app.icon, null, Modifier.size(40.dp))
            else Icon(Icons.Outlined.Apps, null)
        }
        Spacer(Modifier.width(12.dp))
        Column(Modifier.weight(1f)) {
            Text(app.label, maxLines = 1, overflow = TextOverflow.Ellipsis)
            if (isCurrent) Text("현재 기본 앱", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.primary)
        }
        RadioButton(selected = selected, onClick = onClick)
    }
}

@Composable
fun SortDialog(vm: AppViewModel, onDismiss: () -> Unit) {
    var sortSel by remember { mutableStateOf(vm.sortBy) }
    var asc by remember { mutableStateOf(vm.sortAscending) }
    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text("정렬") },
        text = {
            Column {
                SortBy.entries.forEach { s ->
                    Row(
                        Modifier.fillMaxWidth().clip(RoundedCornerShape(8.dp)).clickable { sortSel = s },
                        verticalAlignment = Alignment.CenterVertically,
                    ) {
                        RadioButton(selected = sortSel == s, onClick = { sortSel = s })
                        Text(s.label)
                    }
                }
                Spacer(Modifier.height(8.dp))
                Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    listOf(true to "오름차순", false to "내림차순").forEach { (v, label) ->
                        Row(
                            Modifier.clip(RoundedCornerShape(8.dp)).clickable { asc = v },
                            verticalAlignment = Alignment.CenterVertically,
                        ) {
                            RadioButton(selected = asc == v, onClick = { asc = v })
                            Text(label)
                        }
                    }
                }
            }
        },
        confirmButton = {
            TextButton(onClick = {
                vm.setSort(sortSel, asc)
                onDismiss()
            }) { Text("완료") }
        },
        dismissButton = { TextButton(onClick = onDismiss) { Text("취소") } },
    )
}
