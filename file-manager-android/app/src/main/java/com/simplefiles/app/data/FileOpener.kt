package com.simplefiles.app.data

import android.content.ActivityNotFoundException
import android.content.ComponentName
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.content.pm.ResolveInfo
import android.net.Uri
import android.os.Build
import android.webkit.MimeTypeMap
import androidx.compose.ui.graphics.ImageBitmap
import androidx.compose.ui.graphics.asImageBitmap
import androidx.core.content.FileProvider
import androidx.core.graphics.drawable.toBitmap
import com.simplefiles.core.NameUtil
import java.io.File

data class AppChoice(val component: ComponentName, val label: String, val icon: ImageBitmap?)

/**
 * 파일 열기. 확장자별로 고른 기본 앱을 기억해 두고, 다음부터는 묻지 않고 그 앱으로 연다.
 */
class FileOpener(private val context: Context, private val prefs: Prefs) {
    private val pm: PackageManager get() = context.packageManager
    private val authority = context.packageName + ".fileprovider"

    private val extraMime = mapOf(
        "epub" to "application/epub+zip",
        "hwp" to "application/x-hwp",
        "hwpx" to "application/haansofthwpx",
        "md" to "text/markdown",
        "mkv" to "video/x-matroska",
        "cbz" to "application/vnd.comicbook+zip",
        "mobi" to "application/x-mobipocket-ebook",
        "apk" to "application/vnd.android.package-archive",
        "opus" to "audio/ogg",
        "heic" to "image/heic",
    )

    fun mimeOf(name: String): String {
        val ext = NameUtil.ext(name)
        if (ext.isEmpty()) return "*/*"
        return MimeTypeMap.getSingleton().getMimeTypeFromExtension(ext) ?: extraMime[ext] ?: "*/*"
    }

    fun uriOf(file: File): Uri = FileProvider.getUriForFile(context, authority, file)

    private fun viewIntent(file: File): Intent =
        Intent(Intent.ACTION_VIEW)
            .setDataAndType(uriOf(file), mimeOf(file.name))
            .addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION or Intent.FLAG_GRANT_WRITE_URI_PERMISSION)

    private fun sampleIntent(ext: String): Intent {
        val name = NameUtil.join("sample", ext)
        return Intent(Intent.ACTION_VIEW)
            .setDataAndType(Uri.parse("content://$authority/external/$name"), mimeOf(name))
    }

    private fun query(intent: Intent): List<ResolveInfo> =
        if (Build.VERSION.SDK_INT >= 33) {
            pm.queryIntentActivities(intent, PackageManager.ResolveInfoFlags.of(PackageManager.MATCH_DEFAULT_ONLY.toLong()))
        } else {
            @Suppress("DEPRECATION")
            pm.queryIntentActivities(intent, PackageManager.MATCH_DEFAULT_ONLY)
        }

    /** 이 확장자를 열 수 있는 앱 목록. 느릴 수 있으니 백그라운드에서 호출. */
    fun handlers(ext: String, file: File?): List<AppChoice> {
        val intent = if (file != null) viewIntent(file) else sampleIntent(ext)
        return query(intent)
            .filter { it.activityInfo.packageName != context.packageName }
            .distinctBy { it.activityInfo.packageName + "/" + it.activityInfo.name }
            .map { ri ->
                AppChoice(
                    ComponentName(ri.activityInfo.packageName, ri.activityInfo.name),
                    ri.loadLabel(pm).toString(),
                    runCatching { ri.loadIcon(pm).toBitmap(96, 96).asImageBitmap() }.getOrNull(),
                )
            }
            .sortedBy { it.label }
    }

    fun isAvailable(cn: ComponentName): Boolean = try {
        @Suppress("DEPRECATION")
        pm.getActivityInfo(cn, 0)
        true
    } catch (e: PackageManager.NameNotFoundException) {
        false
    }

    fun appLabel(cn: ComponentName): String = try {
        @Suppress("DEPRECATION")
        pm.getActivityInfo(cn, 0).loadLabel(pm).toString()
    } catch (e: PackageManager.NameNotFoundException) {
        cn.packageName + " (삭제됨)"
    }

    fun appIcon(cn: ComponentName): ImageBitmap? = runCatching {
        pm.getActivityIcon(cn).toBitmap(96, 96).asImageBitmap()
    }.getOrNull()

    /** 저장된 기본 앱 (설치돼 있을 때만) */
    fun defaultFor(ext: String): ComponentName? = prefs.defaultApp(ext)?.takeIf { isAvailable(it) }

    fun launch(file: File, component: ComponentName?): Boolean {
        val intent = viewIntent(file).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
        if (component != null) intent.component = component
        return try {
            context.startActivity(intent)
            true
        } catch (e: ActivityNotFoundException) {
            false
        } catch (e: SecurityException) {
            false
        }
    }

    fun share(files: List<File>): Boolean {
        if (files.isEmpty()) return false
        val uris = ArrayList(files.map { uriOf(it) })
        val mime = files.map { mimeOf(it.name) }.distinct().singleOrNull() ?: "*/*"
        val send = if (uris.size == 1) {
            Intent(Intent.ACTION_SEND).putExtra(Intent.EXTRA_STREAM, uris[0])
        } else {
            Intent(Intent.ACTION_SEND_MULTIPLE).putParcelableArrayListExtra(Intent.EXTRA_STREAM, uris)
        }
        send.type = mime
        send.addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
        val chooser = Intent.createChooser(send, "공유").addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
        return try {
            context.startActivity(chooser)
            true
        } catch (e: ActivityNotFoundException) {
            false
        }
    }
}
