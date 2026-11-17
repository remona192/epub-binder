package com.simplefiles.app.data

import android.Manifest
import android.content.Context
import android.content.pm.PackageManager
import android.os.Build
import android.os.Environment
import android.os.StatFs
import android.os.storage.StorageManager
import java.io.File

data class StorageRoot(val file: File, val label: String, val isPrimary: Boolean)

object Storage {
    fun roots(context: Context): List<StorageRoot> {
        val result = mutableListOf<StorageRoot>()
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.R) {
            val sm = context.getSystemService(StorageManager::class.java)
            for (v in sm.storageVolumes) {
                val dir = v.directory ?: continue
                if (v.state != Environment.MEDIA_MOUNTED) continue
                val label = if (v.isPrimary) "내장 메모리" else (v.getDescription(context) ?: "SD 카드")
                result += StorageRoot(dir, label, v.isPrimary)
            }
        } else {
            context.getExternalFilesDirs(null).filterNotNull().forEachIndexed { i, f ->
                val root = File(f.path.substringBefore("/Android/data/"))
                result += StorageRoot(root, if (i == 0) "내장 메모리" else "SD 카드", i == 0)
            }
        }
        if (result.isEmpty()) {
            @Suppress("DEPRECATION")
            result += StorageRoot(Environment.getExternalStorageDirectory(), "내장 메모리", true)
        }
        return result.sortedByDescending { it.isPrimary }
    }

    fun hasAllFilesAccess(context: Context): Boolean =
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.R) {
            Environment.isExternalStorageManager()
        } else {
            context.checkSelfPermission(Manifest.permission.WRITE_EXTERNAL_STORAGE) == PackageManager.PERMISSION_GRANTED
        }

    /** (사용량, 전체) 바이트 */
    fun space(root: File): Pair<Long, Long> = runCatching {
        val s = StatFs(root.path)
        (s.totalBytes - s.availableBytes) to s.totalBytes
    }.getOrDefault(0L to 0L)
}
