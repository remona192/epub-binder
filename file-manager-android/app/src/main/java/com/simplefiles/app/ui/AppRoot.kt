package com.simplefiles.app.ui

import androidx.activity.compose.BackHandler
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.outlined.Folder
import androidx.compose.material3.Button
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.saveable.rememberSaveableStateHolder
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp

@Composable
fun AppRoot(vm: AppViewModel, onRequestPermission: () -> Unit) {
    if (!vm.hasPermission) {
        PermissionScreen(onRequestPermission)
        return
    }
    BackHandler(enabled = vm.selection.isNotEmpty() || vm.backStack.size > 1) { vm.back() }

    // 화면별 스크롤 위치 등을 기억 (폴더에서 뒤로 왔을 때 위치 유지)
    val holder = rememberSaveableStateHolder()
    val screen = vm.current
    holder.SaveableStateProvider(screen.key) {
        when (screen) {
            Screen.Home -> HomeScreen(vm)
            is Screen.Browser -> BrowserScreen(vm, screen.path)
            is Screen.Category -> CategoryScreen(vm, screen.category)
            Screen.Search -> SearchScreen(vm)
            is Screen.BatchRename -> BatchRenameScreen(vm, screen.paths)
            is Screen.Duplicates -> DuplicatesScreen(vm, screen.scope)
            Screen.Trash -> TrashScreen(vm)
            Screen.Settings -> SettingsScreen(vm)
        }
    }
    GlobalDialogs(vm)
}

@Composable
private fun PermissionScreen(onRequest: () -> Unit) {
    Surface(color = MaterialTheme.colorScheme.background, modifier = Modifier.fillMaxSize()) {
        Column(
            Modifier.fillMaxSize().padding(32.dp),
            verticalArrangement = Arrangement.Center,
            horizontalAlignment = Alignment.CenterHorizontally,
        ) {
            RoundIcon(Icons.Outlined.Folder, TypeColors.folder, 72)
            Spacer(Modifier.height(24.dp))
            Text("모든 파일 접근 권한이 필요합니다", style = MaterialTheme.typography.titleLarge, textAlign = TextAlign.Center)
            Spacer(Modifier.height(12.dp))
            Text(
                "휴대폰 저장공간 전체를 검색하고 파일을 복사·이동·삭제하려면\n'모든 파일 관리 허용'을 켜 주세요.",
                style = MaterialTheme.typography.bodyMedium,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
                textAlign = TextAlign.Center,
            )
            Spacer(Modifier.height(28.dp))
            Button(onClick = onRequest, modifier = Modifier.fillMaxWidth()) { Text("권한 허용하러 가기") }
        }
    }
}
