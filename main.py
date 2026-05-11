import threading
from datetime import datetime

from kivy.app import App
from kivy.clock import Clock
from kivy.metrics import dp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.progressbar import ProgressBar
from kivy.uix.scrollview import ScrollView
from kivy.uix.spinner import Spinner
from kivy.uix.textinput import TextInput

from downloader_core import DownloaderCore


class RootLayout(BoxLayout):
    pass


class YTThumbApp(App):
    def build(self):
        self.title = "YT Thumb Android"
        outdir = self.user_data_dir if DownloaderCore.is_android_runtime() else None
        self.core = DownloaderCore(outdir=outdir)

        root = BoxLayout(orientation="vertical", padding=dp(12), spacing=dp(8))

        root.add_widget(Label(text="YouTube 链接", size_hint_y=None, height=dp(28)))

        self.url_input = TextInput(
            multiline=False,
            hint_text="https://www.youtube.com/watch?v=...",
            size_hint_y=None,
            height=dp(42),
        )
        root.add_widget(self.url_input)

        row = BoxLayout(orientation="horizontal", size_hint_y=None, height=dp(42), spacing=dp(8))
        self.mode_spinner = Spinner(
            text="视频+封面",
            values=("视频+封面", "仅封面", "仅音频"),
            size_hint_x=0.45,
        )
        row.add_widget(self.mode_spinner)

        self.start_btn = Button(text="开始下载", size_hint_x=0.55)
        self.start_btn.bind(on_press=self.on_start)
        row.add_widget(self.start_btn)
        root.add_widget(row)

        self.progress = ProgressBar(max=100, value=0, size_hint_y=None, height=dp(18))
        root.add_widget(self.progress)

        self.status_label = Label(text="就绪", size_hint_y=None, height=dp(24))
        root.add_widget(self.status_label)

        self.out_label = Label(
            text=f"输出目录: {self.core.outdir}",
            size_hint_y=None,
            height=dp(40),
            halign="left",
            valign="middle",
        )
        self.out_label.bind(size=self._sync_label_text)
        root.add_widget(self.out_label)

        root.add_widget(Label(text="日志", size_hint_y=None, height=dp(24)))

        self.log_input = TextInput(readonly=True, multiline=True, size_hint=(1, 1))
        sv = ScrollView(size_hint=(1, 1))
        sv.add_widget(self.log_input)
        root.add_widget(sv)

        self.log("应用已启动")
        self.request_android_permissions()
        return root

    def request_android_permissions(self):
        if not DownloaderCore.is_android_runtime():
            return

        try:
            from android.permissions import Permission, request_permissions

            request_permissions(
                [
                    Permission.READ_EXTERNAL_STORAGE,
                    Permission.WRITE_EXTERNAL_STORAGE,
                ]
            )
        except Exception as e:
            self.log(f"权限请求跳过: {e}")

    def _sync_label_text(self, instance, _):
        instance.text_size = instance.size

    def log(self, msg):
        ts = datetime.now().strftime("%H:%M:%S")
        self.log_input.text += f"[{ts}] {msg}\n"
        self.log_input.cursor = (0, len(self.log_input.text.splitlines()))

    def mode_value(self):
        mapping = {
            "视频+封面": "full",
            "仅封面": "thumbnail",
            "仅音频": "audio",
        }
        return mapping[self.mode_spinner.text]

    def on_start(self, _):
        url = self.url_input.text.strip()
        if not url:
            self.status_label.text = "请输入链接"
            return

        self.start_btn.disabled = True
        self.progress.value = 0
        self.status_label.text = "准备中..."
        self.log("开始任务")

        threading.Thread(target=self.worker, args=(url, self.mode_value()), daemon=True).start()

    def worker(self, url, mode):
        try:
            def cb(evt_type, data):
                Clock.schedule_once(lambda dt: self.on_progress(evt_type, data), 0)

            result = self.core.run(url, mode, cb)
            Clock.schedule_once(lambda dt: self.on_done(result), 0)
        except Exception as e:
            Clock.schedule_once(lambda dt: self.on_error(str(e)), 0)
        finally:
            Clock.schedule_once(lambda dt: self.enable_button(), 0)

    def on_progress(self, evt_type, data):
        if evt_type == "thumbnail_progress":
            self.progress.value = data.get("percent", 0)
            d_k = data.get("downloaded", 0) // 1024
            t_k = data.get("total", 1) // 1024
            self.status_label.text = f"封面下载 {d_k}K/{t_k}K"
            return

        if evt_type == "thumbnail_done":
            self.log(f"封面已保存: {data.get('path')}")
            self.status_label.text = "封面下载完成"
            self.progress.value = 100
            return

        if evt_type == "yt":
            st = data.get("status")
            if st == "downloading":
                total = data.get("total_bytes") or data.get("total_bytes_estimate") or 0
                down = data.get("downloaded_bytes", 0)
                if total:
                    pct = down / total * 100
                    self.progress.value = pct
                    self.status_label.text = f"下载中 {pct:.1f}%"
                else:
                    self.status_label.text = f"下载中 {down // 1024**2}MB"
            elif st == "finished":
                self.status_label.text = "下载完成，正在收尾..."

    def on_done(self, result):
        self.status_label.text = "完成"
        self.progress.value = 100
        self.out_label.text = f"输出目录: {self.core.outdir}"
        self.log("任务完成")
        for k, v in result.items():
            self.log(f"{k}: {v}")

    def on_error(self, msg):
        self.status_label.text = "失败"
        self.log(f"错误: {msg}")

    def enable_button(self):
        self.start_btn.disabled = False


if __name__ == "__main__":
    YTThumbApp().run()
