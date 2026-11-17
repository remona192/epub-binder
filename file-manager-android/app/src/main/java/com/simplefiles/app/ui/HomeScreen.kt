@file:OptIn(ExperimentalMaterial3Api::class)

package com.simplefiles.app.ui

import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.outlined.Android
import androidx.compose.material.icons.outlined.Delete
import androidx.compose.material.icons.outlined.Description
import androidx.compose.material.icons.outlined.Download
import androidx.compose.material.icons.outlined.FileCopy
import androidx.compose.material.icons.outlined.FolderZip
import androidx.compose.material.icons.outlined.Image
import androidx.compose.material.icons.outlined.MoreVert
import androidx.compose.material.icons.outlined.Movie
import androidx.compose.material.icons.outlined.MusicNote
import androidx.compose.material.icons.outlined.PhoneAndroid
import androidx.compose.material.icons.outlined.SdStorage
import androidx.compose.material.icons.outlined.Search
import androidx.compose.material.icons.outlined.Settings
import androidx.compose.material3.DropdownMenu
import androidx.compose.material3.DropdownMenuItem
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Scaffold
import androidx.compose.material3.SnackbarHost
import androidx.compose.material3.Text
import androidx.compose.material3.TopAppBar
import androidx.compose.material3.TopAppBarDefaults
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.simplefiles.app.data.Storage
import com.simplefiles.core.FileCategory
import java.io.File

private data class CategoryTile(val label: String, val icon: ImageVector, val color: Color, val onClick: () -> Unit)

@Composable
fun HomeScreen(vm: AppViewModel) {
    var menu by remember { mutableStateOf(false) }
    val scanning by vm.index.scanning.collectAsState()
    val clip = vm.clipboard
    val primary = vm.roots.firstOrNull()

    Scaffold(
        containerColor = MaterialTheme.colorScheme.background,
        snackbarHost = { SnackbarHost(vm.snackbar) },
        topBar = {
            TopAppBar(
                colors = TopAppBarDefaults.topAppBarColors(containerColor = MaterialTheme.colorScheme.background),
                title = {},
                actions = {
                    IconButton(onClick = { vm.navigate(Screen.Search) }) { Icon(Icons.Outlined.Search, "검색") }
                    Box {
                        IconButton(onClick = { menu = true }) { Icon(Icons.Outlined.MoreVert, "더보기") }
                        DropdownMenu(expanded = menu, onDismissRequest = { menu = false }) {
                            DropdownMenuItem(text = { Text("휴지통") }, onClick = { menu = false; vm.navigate(Screen.Trash) })
                            DropdownMenuItem(text = { Text("설정") }, onClick = { menu = false; vm.navigate(Screen.Settings) })
                        }
                    }
                },
            )
        },
        bottomBar = {
            if (clip != null) {
                PasteBar(clip.mode, clip.paths.size, canPaste = false, onCancel = { vm.cancelClipboard() }, onPaste = {})
            }
        },
    ) { padding ->
        LazyColumn(Modifier.padding(padding).fillMaxSize(), contentPadding = PaddingValues(bottom = 32.dp)) {
            item {
                Column(Modifier.padding(start = 28.dp, top = 36.dp, bottom = 28.dp)) {
                    Text("내 파일", fontSize = 34.sp, fontWeight = FontWeight.Normal)
                    if (scanning) {
                        Spacer(Modifier.height(6.dp))
                        Text("저장공간 색인 중…", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                    }
                }
            }
            item {
                val tiles = listOf(
                    CategoryTile("이미지", Icons.Outlined.Image, TypeColors.image) { vm.navigate(Screen.Category(FileCategory.IMAGES)) },
                    CategoryTile("동영상", Icons.Outlined.Movie, TypeColors.video) { vm.navigate(Screen.Category(FileCategory.VIDEOS)) },
                    CategoryTile("오디오", Icons.Outlined.MusicNote, TypeColors.audio) { vm.navigate(Screen.Category(FileCategory.AUDIO)) },
                    CategoryTile("문서", Icons.Outlined.Description, TypeColors.document) { vm.navigate(Screen.Category(FileCategory.DOCUMENTS)) },
                    CategoryTile("다운로드", Icons.Outlined.Download, TypeColors.download) {
                        primary?.let { vm.navigate(Screen.Browser(File(it.file, "Download").path)) }
                    },
                    CategoryTile("설치 파일", Icons.Outlined.Android, TypeColors.apk) { vm.navigate(Screen.Category(FileCategory.APK)) },
                    CategoryTile("압축 파일", Icons.Outlined.FolderZip, TypeColors.archive) { vm.navigate(Screen.Category(FileCategory.ARCHIVES)) },
                )
                SectionCard {
                    tiles.chunked(4).forEach { row ->
                        Row(Modifier.fillMaxWidth().padding(horizontal = 6.dp, vertical = 4.dp)) {
                            row.forEach { t -> CategoryTileView(t, Modifier.weight(1f)) }
                            repeat(4 - row.size) { Spacer(Modifier.weight(1f)) }
                        }
                    }
                }
            }
            item {
                SectionTitle("저장공간")
                SectionCard {
                    vm.roots.forEachIndexed { i, root ->
                        val (used, total) = remember(root, vm.refreshTick) { Storage.space(root.file) }
                        Row(
                            Modifier.fillMaxWidth().clickable { vm.navigate(Screen.Browser(root.file.path)) }
                                .padding(horizontal = 18.dp, vertical = 14.dp),
                            verticalAlignment = Alignment.CenterVertically,
                        ) {
                            RoundIcon(if (root.isPrimary) Icons.Outlined.PhoneAndroid else Icons.Outlined.SdStorage, MaterialTheme.colorScheme.primary)
                            Spacer(Modifier.width(14.dp))
                            Column(Modifier.weight(1f)) {
                                Row {
                                    Text(root.label, style = MaterialTheme.typography.bodyLarge, modifier = Modifier.weight(1f))
                                    Text(
                                        "${formatSize(used)} / ${formatSize(total)}",
                                        style = MaterialTheme.typography.bodySmall,
                                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                                    )
                                }
                                Spacer(Modifier.height(8.dp))
                                LinearProgressIndicator(
                                    progress = { if (total > 0) used.toFloat() / total else 0f },
                                    modifier = Modifier.fillMaxWidth().height(5.dp).clip(RoundedCornerShape(3.dp)),
                                    trackColor = MaterialTheme.colorScheme.surfaceVariant,
                                    drawStopIndicator = {},
                                )
                            }
                        }
                        if (i != vm.roots.lastIndex) HorizontalDivider(Modifier.padding(start = 74.dp, end = 16.dp), color = MaterialTheme.colorScheme.outlineVariant)
                    }
                }
            }
            item {
                SectionTitle("유틸리티")
                SectionCard {
                    UtilityRow(Icons.Outlined.FileCopy, TypeColors.document, "중복 파일 찾기", "파일명 일치율로 비슷한 파일 찾기") {
                        vm.navigate(Screen.Duplicates(null))
                    }
                    HorizontalDivider(Modifier.padding(start = 74.dp, end = 16.dp), color = MaterialTheme.colorScheme.outlineVariant)
                    UtilityRow(Icons.Outlined.Delete, TypeColors.video, "휴지통", "삭제한 파일은 30일 동안 보관") {
                        vm.navigate(Screen.Trash)
                    }
                    HorizontalDivider(Modifier.padding(start = 74.dp, end = 16.dp), color = MaterialTheme.colorScheme.outlineVariant)
                    UtilityRow(Icons.Outlined.Settings, TypeColors.other, "기본 앱 설정", "확장자별로 파일을 열 앱 지정/변경") {
                        vm.navigate(Screen.Settings)
                    }
                }
            }
        }
    }
}

@Composable
private fun CategoryTileView(t: CategoryTile, modifier: Modifier) {
    Column(
        modifier.clip(RoundedCornerShape(16.dp)).clickable(onClick = t.onClick).padding(vertical = 12.dp),
        horizontalAlignment = Alignment.CenterHorizontally,
    ) {
        RoundIcon(t.icon, t.color, 48)
        Spacer(Modifier.height(8.dp))
        Text(t.label, style = MaterialTheme.typography.bodySmall)
    }
}

@Composable
fun RoundIcon(icon: ImageVector, color: Color, sizeDp: Int = 40) {
    Box(
        Modifier.size(sizeDp.dp).clip(RoundedCornerShape((sizeDp * 0.32f).dp)).background(color.copy(alpha = 0.14f)),
        contentAlignment = Alignment.Center,
    ) {
        Icon(icon, null, tint = color, modifier = Modifier.size((sizeDp * 0.55f).dp))
    }
}

@Composable
private fun UtilityRow(icon: ImageVector, color: Color, title: String, desc: String, onClick: () -> Unit) {
    Row(
        Modifier.fillMaxWidth().clickable(onClick = onClick).padding(horizontal = 18.dp, vertical = 14.dp),
        verticalAlignment = Alignment.CenterVertically,
        horizontalArrangement = Arrangement.Start,
    ) {
        RoundIcon(icon, color)
        Spacer(Modifier.width(14.dp))
        Column {
            Text(title, style = MaterialTheme.typography.bodyLarge)
            Text(desc, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
        }
    }
}
