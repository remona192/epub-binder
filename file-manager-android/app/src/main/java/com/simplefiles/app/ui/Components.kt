@file:OptIn(ExperimentalFoundationApi::class, ExperimentalMaterial3Api::class)

package com.simplefiles.app.ui

import androidx.compose.foundation.ExperimentalFoundationApi
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.combinedClickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ColumnScope
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.RowScope
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.navigationBarsPadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.outlined.DriveFileMove
import androidx.compose.material.icons.outlined.Android
import androidx.compose.material.icons.outlined.Check
import androidx.compose.material.icons.outlined.ContentCopy
import androidx.compose.material.icons.outlined.Delete
import androidx.compose.material.icons.outlined.Description
import androidx.compose.material.icons.outlined.DriveFileRenameOutline
import androidx.compose.material.icons.outlined.Folder
import androidx.compose.material.icons.outlined.FolderZip
import androidx.compose.material.icons.outlined.Image
import androidx.compose.material.icons.outlined.InsertDriveFile
import androidx.compose.material.icons.outlined.MoreVert
import androidx.compose.material.icons.outlined.Movie
import androidx.compose.material.icons.outlined.MusicNote
import androidx.compose.material.icons.outlined.PictureAsPdf
import androidx.compose.material3.DropdownMenu
import androidx.compose.material3.DropdownMenuItem
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.Shape
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.SpanStyle
import androidx.compose.ui.text.buildAnnotatedString
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.text.withStyle
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import coil.compose.AsyncImage
import coil.request.ImageRequest
import com.simplefiles.app.data.FileItem
import com.simplefiles.core.FileCategory
import com.simplefiles.core.TransferMode
import java.io.File
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale

// ---------------- 형식 ----------------

fun formatSize(bytes: Long): String {
    if (bytes < 1024) return "$bytes B"
    val units = arrayOf("KB", "MB", "GB", "TB")
    var v = bytes / 1024.0
    var i = 0
    while (v >= 1024 && i < units.lastIndex) {
        v /= 1024
        i++
    }
    return if (v >= 100) String.format(Locale.ROOT, "%.0f %s", v, units[i])
    else String.format(Locale.ROOT, "%.1f %s", v, units[i])
}

private val dateFmt = SimpleDateFormat("yyyy. M. d. HH:mm", Locale.KOREA)
fun formatDate(ms: Long): String = dateFmt.format(Date(ms))

fun subtitleOf(item: FileItem): String =
    if (item.isDir) {
        formatDate(item.lastModified) + if (item.childCount >= 0) "  ·  ${item.childCount}개 항목" else ""
    } else {
        formatDate(item.lastModified) + "  ·  " + formatSize(item.size)
    }

// ---------------- 카드 ----------------

@Composable
fun SectionTitle(text: String) {
    Text(
        text,
        style = MaterialTheme.typography.titleSmall,
        color = MaterialTheme.colorScheme.onSurfaceVariant,
        modifier = Modifier.padding(start = 28.dp, top = 20.dp, bottom = 8.dp),
    )
}

@Composable
fun SectionCard(modifier: Modifier = Modifier, content: @Composable ColumnScope.() -> Unit) {
    Surface(
        color = cardColor,
        shape = RoundedCornerShape(24.dp),
        modifier = modifier.fillMaxWidth().padding(horizontal = 12.dp),
    ) {
        Column(Modifier.padding(vertical = 6.dp), content = content)
    }
}

/** 목록을 하나의 둥근 카드처럼 보이게: 첫/마지막 항목만 둥글게 */
fun itemShape(index: Int, count: Int): Shape {
    val r = 24.dp
    val top = if (index == 0) r else 0.dp
    val bottom = if (index == count - 1) r else 0.dp
    return RoundedCornerShape(topStart = top, topEnd = top, bottomStart = bottom, bottomEnd = bottom)
}

@Composable
fun Modifier.cardItem(index: Int, count: Int): Modifier =
    this.padding(horizontal = 12.dp).clip(itemShape(index, count)).background(cardColor)

// ---------------- 아이콘 ----------------

data class TypeIcon(val icon: ImageVector, val color: Color)

fun typeIconOf(name: String, isDir: Boolean): TypeIcon {
    if (isDir) return TypeIcon(Icons.Outlined.Folder, TypeColors.folder)
    if (name.endsWith(".pdf", ignoreCase = true)) return TypeIcon(Icons.Outlined.PictureAsPdf, TypeColors.video)
    return when (FileCategory.of(name)) {
        FileCategory.IMAGES -> TypeIcon(Icons.Outlined.Image, TypeColors.image)
        FileCategory.VIDEOS -> TypeIcon(Icons.Outlined.Movie, TypeColors.video)
        FileCategory.AUDIO -> TypeIcon(Icons.Outlined.MusicNote, TypeColors.audio)
        FileCategory.DOCUMENTS -> TypeIcon(Icons.Outlined.Description, TypeColors.document)
        FileCategory.APK -> TypeIcon(Icons.Outlined.Android, TypeColors.apk)
        FileCategory.ARCHIVES -> TypeIcon(Icons.Outlined.FolderZip, TypeColors.archive)
        null -> TypeIcon(Icons.Outlined.InsertDriveFile, TypeColors.other)
    }
}

@Composable
fun FileIcon(name: String, path: String, isDir: Boolean, size: Dp = 44.dp, thumbnail: Boolean = true) {
    val t = typeIconOf(name, isDir)
    val shape = RoundedCornerShape(12.dp)
    Box(
        Modifier.size(size).clip(shape).background(t.color.copy(alpha = 0.14f)),
        contentAlignment = Alignment.Center,
    ) {
        Icon(t.icon, null, tint = t.color, modifier = Modifier.size(size * 0.55f))
        val cat = if (isDir) null else FileCategory.of(name)
        if (thumbnail && (cat == FileCategory.IMAGES || cat == FileCategory.VIDEOS)) {
            val ctx = LocalContext.current
            AsyncImage(
                model = ImageRequest.Builder(ctx).data(File(path)).size(160).build(),
                contentDescription = null,
                contentScale = ContentScale.Crop,
                modifier = Modifier.fillMaxSize(),
            )
        }
    }
}

// ---------------- 파일 한 줄 ----------------

@Composable
fun SelectMark(selected: Boolean) {
    val c = MaterialTheme.colorScheme
    Box(
        Modifier
            .size(24.dp)
            .clip(CircleShape)
            .background(if (selected) c.primary else Color.Transparent)
            .border(2.dp, if (selected) c.primary else c.onSurfaceVariant.copy(alpha = 0.5f), CircleShape),
        contentAlignment = Alignment.Center,
    ) {
        if (selected) Icon(Icons.Outlined.Check, null, tint = c.onPrimary, modifier = Modifier.size(16.dp))
    }
}

@Composable
fun FileRow(
    item: FileItem,
    selectionMode: Boolean,
    selected: Boolean,
    onClick: () -> Unit,
    onLongClick: () -> Unit,
    modifier: Modifier = Modifier,
    subtitle: String = subtitleOf(item),
    highlight: IntRange? = null,
    showDivider: Boolean = true,
) {
    Column(modifier) {
        Row(
            Modifier
                .fillMaxWidth()
                .combinedClickable(onClick = onClick, onLongClick = onLongClick)
                .background(if (selected) MaterialTheme.colorScheme.primary.copy(alpha = 0.08f) else Color.Transparent)
                .padding(horizontal = 16.dp, vertical = 10.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            if (selectionMode) {
                SelectMark(selected)
                Spacer(Modifier.width(14.dp))
            }
            FileIcon(item.name, item.path, item.isDir, thumbnail = !item.inArchive)
            Spacer(Modifier.width(14.dp))
            Column(Modifier.weight(1f)) {
                HighlightedText(item.name, highlight)
                Spacer(Modifier.height(2.dp))
                Text(
                    subtitle,
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                    maxLines = 1,
                    overflow = TextOverflow.Ellipsis,
                )
            }
        }
        if (showDivider) {
            HorizontalDivider(
                Modifier.padding(start = if (selectionMode) 112.dp else 74.dp, end = 16.dp),
                color = MaterialTheme.colorScheme.outlineVariant,
            )
        }
    }
}

@Composable
fun HighlightedText(text: String, range: IntRange?) {
    val primary = MaterialTheme.colorScheme.primary
    val annotated = buildAnnotatedString {
        if (range == null || range.first < 0 || range.last >= text.length) {
            append(text)
        } else {
            append(text.substring(0, range.first))
            withStyle(SpanStyle(color = primary, fontWeight = FontWeight.SemiBold)) {
                append(text.substring(range.first, range.last + 1))
            }
            append(text.substring(range.last + 1))
        }
    }
    Text(annotated, style = MaterialTheme.typography.bodyLarge, maxLines = 2, overflow = TextOverflow.Ellipsis)
}

// ---------------- 하단 바 ----------------

@Composable
fun BottomAction(icon: ImageVector, label: String, enabled: Boolean = true, onClick: () -> Unit) {
    val alpha = if (enabled) 1f else 0.38f
    Column(
        Modifier
            .clip(RoundedCornerShape(12.dp))
            .clickable(enabled = enabled, onClick = onClick)
            .padding(horizontal = 10.dp, vertical = 6.dp),
        horizontalAlignment = Alignment.CenterHorizontally,
    ) {
        Icon(icon, null, tint = MaterialTheme.colorScheme.onSurface.copy(alpha = alpha), modifier = Modifier.size(22.dp))
        Spacer(Modifier.height(2.dp))
        Text(label, fontSize = 11.sp, color = MaterialTheme.colorScheme.onSurface.copy(alpha = alpha), maxLines = 1)
    }
}

@Composable
fun BottomBarSurface(content: @Composable RowScope.() -> Unit) {
    Surface(color = cardColor, shadowElevation = 8.dp) {
        Row(
            Modifier.fillMaxWidth().navigationBarsPadding().padding(horizontal = 8.dp, vertical = 6.dp),
            horizontalArrangement = Arrangement.SpaceEvenly,
            verticalAlignment = Alignment.CenterVertically,
            content = content,
        )
    }
}

data class MoreAction(val label: String, val enabled: Boolean = true, val onClick: () -> Unit)

/** 삼성 내 파일의 하단 선택 바: 이동 · 복사 · 이름 변경 · 삭제 · 더보기 */
@Composable
fun SelectionBottomBar(
    count: Int,
    onMove: () -> Unit,
    onCopy: () -> Unit,
    onRename: () -> Unit,
    onDelete: () -> Unit,
    more: List<MoreAction>,
) {
    var menu by remember { mutableStateOf(false) }
    BottomBarSurface {
        BottomAction(Icons.Outlined.DriveFileMove, "이동", count > 0, onMove)
        BottomAction(Icons.Outlined.ContentCopy, "복사", count > 0, onCopy)
        BottomAction(Icons.Outlined.DriveFileRenameOutline, if (count > 1) "일괄 이름 변경" else "이름 변경", count > 0, onRename)
        BottomAction(Icons.Outlined.Delete, "삭제", count > 0, onDelete)
        Box {
            BottomAction(Icons.Outlined.MoreVert, "더보기", count > 0) { menu = true }
            DropdownMenu(expanded = menu, onDismissRequest = { menu = false }) {
                more.forEach { a ->
                    DropdownMenuItem(
                        text = { Text(a.label) },
                        enabled = a.enabled,
                        onClick = {
                            menu = false
                            a.onClick()
                        },
                    )
                }
            }
        }
    }
}

/** 복사/이동할 위치를 고르는 동안 보이는 바 */
@Composable
fun PasteBar(mode: TransferMode, count: Int, canPaste: Boolean, onCancel: () -> Unit, onPaste: () -> Unit) {
    Surface(color = cardColor, shadowElevation = 8.dp) {
        Column(Modifier.fillMaxWidth().navigationBarsPadding().padding(horizontal = 16.dp, vertical = 8.dp)) {
            Text(
                if (canPaste) "${count}개 항목 · ${if (mode == TransferMode.COPY) "복사" else "이동"}할 폴더를 열고 아래 버튼을 누르세요"
                else "${count}개 항목 · 저장공간에서 폴더를 선택하세요",
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
            Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceEvenly) {
                TextButton(onClick = onCancel, modifier = Modifier.weight(1f)) { Text("취소") }
                TextButton(onClick = onPaste, enabled = canPaste, modifier = Modifier.weight(1f)) {
                    Text(if (mode == TransferMode.COPY) "여기에 복사" else "여기로 이동", fontWeight = FontWeight.SemiBold)
                }
            }
        }
    }
}

@Composable
fun EmptyState(text: String, modifier: Modifier = Modifier) {
    Box(modifier.fillMaxWidth().padding(vertical = 80.dp), contentAlignment = Alignment.Center) {
        Text(text, color = MaterialTheme.colorScheme.onSurfaceVariant)
    }
}

val listBottomPadding = PaddingValues(bottom = 24.dp)
