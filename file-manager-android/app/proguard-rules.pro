# Compose/Coil ship their own consumer rules.
-dontwarn org.jetbrains.annotations.**
# commons-compress: 선택적 의존성(zstd, brotli 등)은 쓰지 않는다
-dontwarn org.apache.commons.compress.**
-dontwarn com.github.luben.zstd.**
-dontwarn org.brotli.**
-dontwarn org.objectweb.asm.**
-dontwarn org.osgi.**
-dontwarn javax.**
-dontwarn java.lang.invoke.**
-keep class org.apache.commons.compress.archivers.sevenz.** { *; }
-keep class org.apache.commons.compress.archivers.zip.** { *; }
-keep class org.tukaani.xz.** { *; }
