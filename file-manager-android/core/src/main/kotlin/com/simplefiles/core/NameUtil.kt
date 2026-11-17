package com.simplefiles.core

import java.io.File

object NameUtil {
    /** "a.tar.gz" -> ("a.tar", "gz"), ".nomedia" -> (".nomedia", ""), "noext" -> ("noext", "") */
    fun splitExt(name: String): Pair<String, String> {
        val dot = name.lastIndexOf('.')
        if (dot <= 0 || dot == name.length - 1) return name to ""
        return name.substring(0, dot) to name.substring(dot + 1)
    }

    fun ext(name: String): String = splitExt(name).second.lowercase()

    fun join(base: String, ext: String): String = if (ext.isEmpty()) base else "$base.$ext"

    /** 폴더 안에 없는 이름을 만든다: "사진.jpg" -> "사진 (1).jpg", 폴더는 확장자를 나누지 않는다. */
    fun uniqueName(dir: File, name: String, isDir: Boolean): String {
        if (!File(dir, name).exists()) return name
        val (base, ext) = if (isDir) name to "" else splitExt(name)
        var n = 1
        while (true) {
            val candidate = join("$base ($n)", ext)
            if (!File(dir, candidate).exists()) return candidate
            n++
        }
    }

    /** 사용할 수 없는 이름이면 이유를, 괜찮으면 null. */
    fun invalidReason(name: String): String? = when {
        name.isBlank() -> "이름이 비어 있습니다"
        name == "." || name == ".." -> "사용할 수 없는 이름입니다"
        name.any { it == '/' || it == '\u0000' } -> "'/' 문자는 사용할 수 없습니다"
        name.any { it in "\\:*?\"<>|" } -> "\\ : * ? \" < > | 문자는 사용할 수 없습니다"
        name.toByteArray(Charsets.UTF_8).size > 255 -> "이름이 너무 깁니다"
        else -> null
    }

    fun isInside(child: File, parent: File): Boolean {
        val c = child.absoluteFile.normalize().path
        val p = parent.absoluteFile.normalize().path
        return c == p || c.startsWith(p.trimEnd('/') + "/")
    }
}
