@file:OptIn(ExperimentalMaterial3Api::class)

package com.simplefiles.app.ui

import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.navigationBarsPadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.itemsIndexed
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material3.Button
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Slider
import androidx.compose.material3.SnackbarHost
import androidx.compose.material3.Surface
import androidx.compose.material3.Switch
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.TopAppBar
import androidx.compose.material3.TopAppBarDefaults
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import java.io.File
import kotlin.math.roundToInt

/** 파일명 일치율(기본 90%) 기준 중복 파일 찾기 */
@Composable
fun DuplicatesScreen(vm: AppViewModel, scope: String?) {
    val ready by vm.index.ready.collectAsState()
    val entries by vm.index.entries.collectAsState()
    val opts = vm.dupOptions
    val groups = vm.dupGroups
    val selected = vm.dupSelected.toSet()

    Scaffold(
        containerColor = MaterialTheme.colorScheme.background,
        snackbarHost = { SnackbarHost(vm.snackbar) },
        topBar = {
            TopAppBar(
                colors = TopAppBarDefaults.topAppBarColors(containerColor = MaterialTheme.colorScheme.background),
                navigationIcon = { IconButton(onClick = { vm.back() }) { Icon(Icons.AutoMirrored.Filled.ArrowBack, "뒤로") } },
                title = { Text("중복 파일 찾기") },
            )
        },
        bottomBar = {
            if (selected.isNotEmpty()) {
                Surface(color = cardColor, shadowElevation = 8.dp) {
                    Row(
                        Modifier.fillMaxWidth().navigationBarsPadding().padding(horizontal = 16.dp, vertical = 10.dp),
                        verticalAlignment = Alignment.CenterVertically,
                    ) {
                        Text("${selected.size}개 선택", modifier = Modifier.weight(1f))
                        TextButton(onClick = { vm.dupSelected.clear() }) { Text("선택 해제") }
                        Button(onClick = { vm.requestDelete(vm.dupSelected.toList()) }) { Text("삭제") }
                    }
                }
            }
        },
    ) { padding ->
        LazyColumn(Modifier.padding(padding).fillMaxSize(), contentPadding = PaddingValues(bottom = 24.dp)) {
            item {
                SectionCard {
                    Column(Modifier.padding(horizontal = 16.dp, vertical = 6.dp)) {
                        Text("검사 범위", style = MaterialTheme.typography.labelMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
                        Text(if (scope == null) "휴대폰 전체 저장공간" else vm.displayPath(scope))
                        Spacer(Modifier.height(12.dp))
                        Row(verticalAlignment = Alignment.CenterVertically) {
                            Text("파일명 일치율", modifier = Modifier.weight(1f))
                            Text("${(opts.threshold * 100).roundToInt()}% 이상", fontWeight = FontWeight.SemiBold, color = MaterialTheme.colorScheme.primary)
                        }
                        Slider(
                            value = (opts.threshold * 100).toFloat(),
                            onValueChange = { vm.dupOptions = opts.copy(threshold = it.roundToInt() / 100.0) },
                            valueRange = 60f..100f,
                            steps = 39,
                        )
                    }
                    OptionSwitch("같은 확장자끼리만 비교", "책.epub 과 책.pdf 는 따로 봅니다", opts.sameExtension) {
                        vm.dupOptions = opts.copy(sameExtension = it)
                    }
                    OptionSwitch("숫자가 다르면 제외", "1권/2권, 01화/02화처럼 번호만 다른 파일은 중복이 아님", opts.excludeDifferentNumbers) {
                        vm.dupOptions = opts.copy(excludeDifferentNumbers = it)
                    }
                    OptionSwitch("사본 표기 무시", "'이름 (1)', '이름 - 복사본' 을 원본과 같은 이름으로 봄", opts.ignoreCopyMarkers) {
                        vm.dupOptions = opts.copy(ignoreCopyMarkers = it)
                    }
                    Column(Modifier.padding(horizontal = 16.dp, vertical = 8.dp)) {
                        if (vm.dupRunning) {
                            Text(
                                if (!ready) "저장공간을 읽는 중… (${entries.size}개)" else "비교 중… ${(vm.dupProgress * 100).roundToInt()}%",
                                style = MaterialTheme.typography.bodySmall,
                            )
                            Spacer(Modifier.height(6.dp))
                            if (ready) LinearProgressIndicator(progress = { vm.dupProgress }, modifier = Modifier.fillMaxWidth())
                            else LinearProgressIndicator(Modifier.fillMaxWidth())
                            Spacer(Modifier.height(6.dp))
                            OutlinedButton(onClick = { vm.cancelDuplicates() }, modifier = Modifier.fillMaxWidth()) { Text("중지") }
                        } else {
                            Button(onClick = { vm.runDuplicates(scope) }, modifier = Modifier.fillMaxWidth()) {
                                Text(if (groups == null) "검사 시작" else "다시 검사")
                            }
                        }
                    }
                }
            }

            if (groups != null) {
                item {
                    Row(Modifier.fillMaxWidth().padding(start = 28.dp, end = 16.dp, top = 16.dp), verticalAlignment = Alignment.CenterVertically) {
                        Text(
                            if (groups.isEmpty()) "비슷한 이름의 파일이 없습니다"
                            else "${groups.size}개 그룹 · ${groups.sumOf { it.members.size }}개 파일",
                            style = MaterialTheme.typography.titleSmall,
                            modifier = Modifier.weight(1f),
                        )
                        if (groups.isNotEmpty()) {
                            TextButton(onClick = { vm.dupSelectAllButNewest() }) { Text("최신 1개만 남기고 선택") }
                        }
                    }
                }
                itemsIndexed(groups) { gi, g ->
                    Spacer(Modifier.height(8.dp))
                    SectionCard {
                        Text(
                            "그룹 ${gi + 1} · ${g.members.size}개",
                            style = MaterialTheme.typography.labelMedium,
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                            modifier = Modifier.padding(start = 16.dp, top = 6.dp, bottom = 2.dp),
                        )
                        g.members.forEachIndexed { mi, m ->
                            val f = m.file
                            Row(
                                Modifier.fillMaxWidth().clickable { vm.toggleDup(f.path) }.padding(horizontal = 16.dp, vertical = 8.dp),
                                verticalAlignment = Alignment.CenterVertically,
                            ) {
                                SelectMark(f.path in selected)
                                Spacer(Modifier.width(12.dp))
                                androidx.compose.foundation.layout.Box(Modifier.clickable { vm.openFile(File(f.path)) }) {
                                    FileIcon(f.name, f.path, false, 40.dp)
                                }
                                Spacer(Modifier.width(12.dp))
                                Column(Modifier.weight(1f)) {
                                    Text(f.name, maxLines = 2, overflow = TextOverflow.Ellipsis)
                                    Text(
                                        "${formatSize(f.size)} · ${formatDate(f.lastModified)}",
                                        style = MaterialTheme.typography.bodySmall,
                                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                                    )
                                    Text(
                                        vm.displayPath(File(f.path).parent ?: ""),
                                        style = MaterialTheme.typography.bodySmall,
                                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                                        maxLines = 1,
                                        overflow = TextOverflow.Ellipsis,
                                    )
                                }
                                Text(
                                    if (mi == 0) "최신" else "${(m.similarity * 100).roundToInt()}%",
                                    style = MaterialTheme.typography.labelMedium,
                                    color = MaterialTheme.colorScheme.primary,
                                )
                            }
                            if (mi != g.members.lastIndex) {
                                HorizontalDivider(Modifier.padding(start = 100.dp, end = 16.dp), color = MaterialTheme.colorScheme.outlineVariant)
                            }
                        }
                    }
                }
            }
        }
    }
}

@Composable
private fun OptionSwitch(title: String, desc: String, checked: Boolean, onChange: (Boolean) -> Unit) {
    Row(
        Modifier.fillMaxWidth().clickable { onChange(!checked) }.padding(horizontal = 16.dp, vertical = 8.dp),
        verticalAlignment = Alignment.CenterVertically,
        horizontalArrangement = Arrangement.SpaceBetween,
    ) {
        Column(Modifier.weight(1f)) {
            Text(title)
            Text(desc, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
        }
        Switch(checked = checked, onCheckedChange = onChange)
    }
}
