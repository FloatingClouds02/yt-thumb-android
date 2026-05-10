# yt-thumb-android

这是你 `yt-thumb.py` 的安卓 APK 版本工程（Kivy）。

## 功能
- 视频+封面
- 仅封面
- 仅音频

## 说明
- 为了提高 APK 打包稳定性，当前安卓版本不依赖 ffmpeg。
- 所以：
  - 视频模式使用 `best[ext=mp4]/best`（不做音视频二次合并）
  - 音频模式下载原始最佳音频（通常是 `m4a`），不转 `mp3`

## 一键云端出包（推荐）
1. 把这个目录上传到 GitHub 新仓库（分支 `main`）。
2. 打开仓库 `Actions`。
3. 运行工作流：`Build Android APK`。
4. 构建完成后在 `Artifacts` 下载 `yt-thumb-apk`，里面就是 `apk`。

## 本地 Linux 出包（可选）
```bash
pip install buildozer
buildozer android debug
```

## 目录
- `main.py`：安卓界面
- `downloader_core.py`：下载核心逻辑
- `buildozer.spec`：打包配置
- `.github/workflows/build-apk.yml`：GitHub Actions 自动打包
