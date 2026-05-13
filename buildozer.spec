[app]
title = YT Thumb Android
package.name = ytthumb
package.domain = com.ginoyou
source.dir = .
source.include_exts = py,png,jpg,html,css,js,txt
version = 0.1.2
p4a.bootstrap = webview
p4a.port = 5000
requirements = python3,webviewjni,requests,yt-dlp
orientation = portrait
fullscreen = 0
android.permissions = INTERNET
android.accept_sdk_license = True

[buildozer]
log_level = 2
warn_on_root = 1
