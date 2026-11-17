@file:OptIn(ExperimentalMaterial3Api::class)

package com.simplefiles.app.ui

import androidx.compose.foundation.Image
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.outlined.Apps
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Scaffold
import androidx.compose.material3.SnackbarHost
import androidx.compose.material3.Switch
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.TopAppBar
import androidx.compose.material3.TopAppBarDefaults
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.produceState
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext

@Composable
fun SettingsScreen(vm: AppViewModel) {
    val defaults by produceState(emptyList<DefaultAppUi>(), vm.defaultAppsVersion) {
        value = withContext(Dispatchers.IO) { vm.defaultApps() }
    }
    val entries by vm.index.entries.collectAsState()
    val scanning by vm.index.scanning.collectAsState()
    var addExt by remember { mutableStateOf(false) }

    Scaffold(
        containerColor = MaterialTheme.colorScheme.background,
        snackbarHost = { SnackbarHost(vm.snackbar) },
        topBar = {
            TopAppBar(
                colors = TopAppBarDefaults.topAppBarColors(containerColor = MaterialTheme.colorScheme.background),
                navigationIcon = { IconButton(onClick = { vm.back() }) { Icon(Icons.AutoMirrored.Filled.ArrowBack, "뒤로") } },
                title = { Text("설정") },
            )
        },
    ) { padding ->
        LazyColumn(Modifier.padding(padding).fillMaxSize(), contentPadding = PaddingValues(bottom = 32.dp)) {
            item {
                SectionTitle("기본 앱 (파일을 누르면 바로 열 앱)")
                SectionCard {
                    if (defaults.isEmpty()) {
                        Text(
                            "아직 지정한 앱이 없습니다. 파일을 열 때 '항상'을 누르면 여기에 추가됩니다.",
                            style = MaterialTheme.typography.bodySmall,
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                            modifier = Modifier.padding(16.dp),
                        )
                    }
                    defaults.forEachIndexed { i, d ->
                        Row(
                            Modifier.fillMaxWidth().clickable { vm.showChooser(null, d.ext) }.padding(start = 16.dp, end = 4.dp, top = 8.dp, bottom = 8.dp),
                            verticalAlignment = Alignment.CenterVertically,
                        ) {
                            Box(Modifier.size(36.dp), contentAlignment = Alignment.Center) {
                                if (d.icon != null) Image(d.icon, null, Modifier.size(36.dp)) else Icon(Icons.Outlined.Apps, null)
                            }
                            Spacer(Modifier.width(12.dp))
                            Column(Modifier.weight(1f)) {
                                Text(vm.extLabel(d.ext) + " 파일")
                                Text(d.label, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.primary,
                                    maxLines = 1, overflow = TextOverflow.Ellipsis)
                            }
                            TextButton(onClick = { vm.showChooser(null, d.ext) }) { Text("변경") }
                            TextButton(onClick = { vm.clearDefaultApp(d.ext) }) { Text("해제") }
                        }
                        if (i != defaults.lastIndex) HorizontalDivider(Modifier.padding(start = 64.dp, end = 16.dp), color = MaterialTheme.colorScheme.outlineVariant)
                    }
                    TextButton(onClick = { addExt = true }, modifier = Modifier.padding(horizontal = 8.dp)) { Text("+ 확장자별 앱 지정") }
                }
                Text(
                    "파일을 길게 눌러 더보기 › 다른 앱으로 열기에서도 기본 앱을 바꿀 수 있습니다.",
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                    modifier = Modifier.padding(horizontal = 28.dp, vertical = 6.dp),
                )
            }
            item {
                SectionTitle("일반")
                SectionCard {
                    SettingSwitch("휴지통 사용", "삭제한 파일을 30일 동안 보관합니다", vm.useTrash) { vm.toggleUseTrash() }
                    SettingSwitch("숨김 파일 표시", "이름이 . 으로 시작하는 파일과 폴더", vm.showHidden) { vm.toggleShowHidden() }
                }
            }
            item {
                SectionTitle("검색 색인")
                SectionCard {
                    Row(Modifier.fillMaxWidth().padding(horizontal = 16.dp, vertical = 8.dp), verticalAlignment = Alignment.CenterVertically) {
                        Column(Modifier.weight(1f)) {
                            Text("저장공간 전체 색인")
                            Text(
                                (if (scanning) "색인 중… " else "") + "${entries.size}개 항목",
                                style = MaterialTheme.typography.bodySmall,
                                color = MaterialTheme.colorScheme.onSurfaceVariant,
                            )
                        }
                        TextButton(onClick = { vm.rebuildIndex() }, enabled = !scanning) { Text("다시 색인") }
                    }
                }
            }
        }
    }

    if (addExt) {
        var ext by remember { mutableStateOf("") }
        AlertDialog(
            onDismissRequest = { addExt = false },
            title = { Text("확장자 입력") },
            text = {
                OutlinedTextField(value = ext, onValueChange = { ext = it.trim().trimStart('.') }, singleLine = true,
                    placeholder = { Text("예: epub, txt, pdf") })
            },
            confirmButton = {
                TextButton(enabled = ext.isNotBlank(), onClick = {
                    addExt = false
                    vm.showChooser(null, ext.lowercase())
                }) { Text("앱 고르기") }
            },
            dismissButton = { TextButton(onClick = { addExt = false }) { Text("취소") } },
        )
    }
}

@Composable
private fun SettingSwitch(title: String, desc: String, checked: Boolean, onToggle: () -> Unit) {
    Row(
        Modifier.fillMaxWidth().clickable(onClick = onToggle).padding(horizontal = 16.dp, vertical = 10.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Column(Modifier.weight(1f)) {
            Text(title)
            Text(desc, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
        }
        Switch(checked = checked, onCheckedChange = { onToggle() })
    }
}
