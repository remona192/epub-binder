package com.simplefiles.app.ui

import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.darkColorScheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.ui.graphics.Color

// 삼성 One UI '내 파일' 느낌의 담백한 색
private val Light = lightColorScheme(
    primary = Color(0xFF3E7BFA),
    onPrimary = Color.White,
    primaryContainer = Color(0xFFDDE7FF),
    onPrimaryContainer = Color(0xFF0B2A6B),
    secondaryContainer = Color(0xFFE3EAFB),
    background = Color(0xFFF6F6F8),
    onBackground = Color(0xFF111114),
    surface = Color(0xFFF6F6F8),
    onSurface = Color(0xFF111114),
    surfaceVariant = Color(0xFFEDEDF1),
    onSurfaceVariant = Color(0xFF7B7B83),
    surfaceContainerLowest = Color.White,
    surfaceContainerLow = Color.White,
    surfaceContainer = Color.White,
    surfaceContainerHigh = Color.White,
    surfaceContainerHighest = Color(0xFFEDEDF1),
    outlineVariant = Color(0xFFE6E6EA),
    error = Color(0xFFE5484D),
)

private val Dark = darkColorScheme(
    primary = Color(0xFF7AA4FF),
    onPrimary = Color(0xFF002A77),
    primaryContainer = Color(0xFF1E3566),
    onPrimaryContainer = Color(0xFFDDE7FF),
    secondaryContainer = Color(0xFF26324A),
    background = Color(0xFF000000),
    onBackground = Color(0xFFF2F2F5),
    surface = Color(0xFF000000),
    onSurface = Color(0xFFF2F2F5),
    surfaceVariant = Color(0xFF26262B),
    onSurfaceVariant = Color(0xFF9C9CA4),
    surfaceContainerLowest = Color(0xFF17171A),
    surfaceContainerLow = Color(0xFF17171A),
    surfaceContainer = Color(0xFF17171A),
    surfaceContainerHigh = Color(0xFF202024),
    surfaceContainerHighest = Color(0xFF2A2A2F),
    outlineVariant = Color(0xFF2C2C31),
    error = Color(0xFFFF6B6F),
)

@Composable
fun AppTheme(content: @Composable () -> Unit) {
    MaterialTheme(colorScheme = if (isSystemInDarkTheme()) Dark else Light, content = content)
}

/** 카드(흰 둥근 상자) 배경 */
val cardColor: Color @Composable get() = MaterialTheme.colorScheme.surfaceContainerLowest

object TypeColors {
    val folder = Color(0xFFFFB938)
    val image = Color(0xFF8E6CFF)
    val video = Color(0xFFFF5A5F)
    val audio = Color(0xFFFF8A3D)
    val document = Color(0xFF3E7BFA)
    val apk = Color(0xFF2EBD85)
    val archive = Color(0xFF8D6E63)
    val download = Color(0xFF1FB6C9)
    val other = Color(0xFF9E9EA6)
}
