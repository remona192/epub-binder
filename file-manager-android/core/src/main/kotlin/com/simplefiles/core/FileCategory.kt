package com.simplefiles.core

enum class FileCategory(val label: String, val exts: Set<String>) {
    IMAGES("이미지", setOf("jpg", "jpeg", "png", "gif", "webp", "heic", "heif", "bmp", "dng")),
    VIDEOS("동영상", setOf("mp4", "mkv", "avi", "mov", "webm", "3gp", "m4v", "wmv", "flv", "ts")),
    AUDIO("오디오", setOf("mp3", "m4a", "aac", "flac", "wav", "ogg", "opus", "wma", "amr", "mid")),
    DOCUMENTS(
        "문서",
        setOf(
            "pdf", "txt", "epub", "doc", "docx", "xls", "xlsx", "ppt", "pptx", "hwp", "hwpx",
            "md", "csv", "rtf", "odt", "html", "htm", "json", "xml", "cbz", "mobi",
        ),
    ),
    APK("설치 파일", setOf("apk", "apks", "xapk")),
    ARCHIVES("압축 파일", setOf("zip", "rar", "7z", "tar", "gz", "alz", "egg"));

    companion object {
        fun of(name: String): FileCategory? {
            val e = NameUtil.ext(name)
            if (e.isEmpty()) return null
            return entries.firstOrNull { e in it.exts }
        }
    }
}
