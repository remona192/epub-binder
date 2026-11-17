package com.simplefiles.app.data

import android.content.ComponentName
import android.content.Context

class Prefs(context: Context) {
    private val sp = context.getSharedPreferences("settings", Context.MODE_PRIVATE)

    /** 확장자별 기본 앱 (예: "epub" -> 리더 앱). 확장자가 없는 파일은 "" 키. */
    fun defaultApp(ext: String): ComponentName? =
        sp.getString(APP_PREFIX + ext, null)?.let { ComponentName.unflattenFromString(it) }

    fun setDefaultApp(ext: String, component: ComponentName?) {
        sp.edit().apply {
            if (component == null) remove(APP_PREFIX + ext) else putString(APP_PREFIX + ext, component.flattenToString())
        }.apply()
    }

    fun allDefaultApps(): Map<String, ComponentName> =
        sp.all.mapNotNull { (k, v) ->
            if (!k.startsWith(APP_PREFIX) || v !is String) null
            else ComponentName.unflattenFromString(v)?.let { k.removePrefix(APP_PREFIX) to it }
        }.toMap()

    var sortBy: SortBy
        get() = runCatching { SortBy.valueOf(sp.getString("sort_by", null) ?: "NAME") }.getOrDefault(SortBy.NAME)
        set(v) = sp.edit().putString("sort_by", v.name).apply()

    var sortAscending: Boolean
        get() = sp.getBoolean("sort_asc", true)
        set(v) = sp.edit().putBoolean("sort_asc", v).apply()

    var showHidden: Boolean
        get() = sp.getBoolean("show_hidden", false)
        set(v) = sp.edit().putBoolean("show_hidden", v).apply()

    var useTrash: Boolean
        get() = sp.getBoolean("use_trash", true)
        set(v) = sp.edit().putBoolean("use_trash", v).apply()

    companion object {
        private const val APP_PREFIX = "app_"
    }
}
