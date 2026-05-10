[app]
title = YT Thumb Android
package.name = ytthumb
package.domain = com.ginoyou
source.dir = .
source.include_exts = py,png,jpg,kv,atlas,txt
version = 0.1.0
requirements = python3,kivy,requests,yt-dlp
orientation = portrait
fullscreen = 0
android.permissions = INTERNET,WRITE_EXTERNAL_STORAGE,READ_EXTERNAL_STORAGE

[buildozer]
log_level = 2
warn_on_root = 1
