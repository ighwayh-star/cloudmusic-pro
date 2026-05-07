#!/usr/bin/env python3
"""网易云日语歌词提取器 — GUI 窗口"""

import platform
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from lyrics import format_lyrics_text, get_current_song, get_lyrics, search_song

_FONT = ("Microsoft YaHei", 11) if platform.system() == "Windows" else ("sans-serif", 11)


class LyricsApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("网易云日语歌词提取器")
        self.root.geometry("700x700")
        self.root.minsize(500, 500)
        self.songs: list[dict] = []
        self.current_lyrics: dict | None = None
        self._build_ui()

    # ── UI layout ──────────────────────────────────────────────

    def _build_ui(self):
        # -- top: search bar --
        top = ttk.Frame(self.root, padding=8)
        top.pack(fill=tk.X)

        ttk.Label(top, text="搜索歌曲:").pack(side=tk.LEFT)
        self.search_var = tk.StringVar()
        self.search_entry = ttk.Entry(top, textvariable=self.search_var, width=30)
        self.search_entry.pack(side=tk.LEFT, padx=(6, 6))
        self.search_entry.bind("<Return>", lambda _e: self._do_search())

        self.search_btn = ttk.Button(top, text="搜索", command=self._do_search)
        self.search_btn.pack(side=tk.LEFT)

        self.current_btn = ttk.Button(
            top, text="当前播放", command=self._do_current
        )
        self.current_btn.pack(side=tk.LEFT, padx=(6, 0))

        # -- result list --
        list_frame = ttk.Frame(self.root, padding=8)
        list_frame.pack(fill=tk.X)

        ttk.Label(list_frame, text="搜索结果:").pack(anchor=tk.W)

        lb_frame = ttk.Frame(list_frame)
        lb_frame.pack(fill=tk.X, pady=(2, 0))

        self.listbox = tk.Listbox(lb_frame, height=6, exportselection=False)
        h_scroll = ttk.Scrollbar(lb_frame, orient=tk.HORIZONTAL, command=self.listbox.xview)
        self.listbox.configure(xscrollcommand=h_scroll.set)

        self.listbox.grid(row=0, column=0, sticky="ew")
        h_scroll.grid(row=1, column=0, sticky="ew")
        lb_frame.columnconfigure(0, weight=1)
        self.listbox.bind("<<ListboxSelect>>", self._on_select)

        # -- lyrics display --
        disp_label = ttk.Frame(self.root, padding=(8, 0))
        disp_label.pack(fill=tk.X)
        ttk.Label(disp_label, text="歌词:").pack(anchor=tk.W)

        disp_frame = ttk.Frame(self.root, padding=8)
        disp_frame.pack(fill=tk.BOTH, expand=True)

        self.lyrics_text = tk.Text(
            disp_frame, wrap=tk.WORD, state=tk.DISABLED,
            font=_FONT
        )
        scroll = ttk.Scrollbar(disp_frame, command=self.lyrics_text.yview)
        self.lyrics_text.configure(yscrollcommand=scroll.set)

        self.lyrics_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scroll.pack(side=tk.RIGHT, fill=tk.Y)

        # -- bottom bar --
        bottom = ttk.Frame(self.root, padding=8)
        bottom.pack(fill=tk.X)

        self.export_btn = ttk.Button(
            bottom, text="导出 Markdown", command=self._export, state=tk.DISABLED
        )
        self.export_btn.pack(side=tk.LEFT)

        self.status_var = tk.StringVar()
        ttk.Label(bottom, textvariable=self.status_var).pack(side=tk.RIGHT)

    # ── actions ────────────────────────────────────────────────

    def _do_search(self):
        keyword = self.search_var.get().strip()
        if not keyword:
            return

        self.search_btn.configure(state=tk.DISABLED, text="搜索中...")
        self.listbox.delete(0, tk.END)
        self.songs.clear()

        def _run():
            try:
                self.songs = search_song(keyword)
            finally:
                self.root.after(0, self._on_search_done)

        threading.Thread(target=_run, daemon=True).start()

    def _on_search_done(self):
        self.search_btn.configure(state=tk.NORMAL, text="搜索")
        if not self.songs:
            self.listbox.insert(tk.END, "(无结果)")
            self.status_var.set("没找到歌曲")
            return

        for s in self.songs:
            album = f" [{s['album']}]" if s['album'] else ""
            self.listbox.insert(tk.END, f"{s['name']} — {s['artists']}{album}")

        self.status_var.set(f"找到 {len(self.songs)} 首，请选择")

    def _do_current(self):
        """Auto-detect currently playing song from NCM client."""
        self.current_btn.configure(state=tk.DISABLED, text="检测中...")
        self.listbox.delete(0, tk.END)
        self.songs.clear()
        self.status_var.set("正在检测播放器...")

        def _run():
            try:
                info = get_current_song()
            except Exception:
                info = None

            if not info:
                self.root.after(0, lambda: self._on_current_done(None))
                return

            keyword = f"{info['name']} {info['artists']}".strip()
            try:
                results = search_song(keyword)
            except Exception:
                results = []
            self.root.after(0, lambda: self._on_current_done(results))

        threading.Thread(target=_run, daemon=True).start()

    def _on_current_done(self, results: list[dict] | None):
        self.current_btn.configure(state=tk.NORMAL, text="当前播放")
        if results is None:
            self.listbox.insert(tk.END, "(未检测到网易云客户端或未在播放)")
            self.status_var.set("未检测到播放内容")
            return

        if not results:
            self.listbox.insert(tk.END, "(搜索无结果)")
            self.status_var.set("没找到匹配歌曲")
            return

        self.songs = results
        for s in self.songs:
            album = f" [{s['album']}]" if s['album'] else ""
            self.listbox.insert(tk.END, f"{s['name']} — {s['artists']}{album}")

        # Auto-select first result
        self.listbox.selection_set(0)
        self.listbox.activate(0)
        self._on_select()
        self.status_var.set(f"已自动选择第一首，找到 {len(results)} 首")

    def _on_select(self, _event=None):
        sel = self.listbox.curselection()
        if not sel:
            return
        idx = sel[0]
        if idx >= len(self.songs):
            return

        song = self.songs[idx]
        self.status_var.set(f"加载中: {song['name']}...")
        self.export_btn.configure(state=tk.DISABLED)

        def _run():
            try:
                lrc = get_lyrics(song["id"])
            except Exception:
                lrc = None
            self.root.after(0, lambda: self._on_lyrics_done(song, lrc))

        threading.Thread(target=_run, daemon=True).start()

    def _on_lyrics_done(self, song: dict, lrc: dict | None):
        self.lyrics_text.configure(state=tk.NORMAL)
        self.lyrics_text.delete("1.0", tk.END)

        if not lrc or not any(lrc.values()):
            self.lyrics_text.insert(tk.END, "(这首歌暂无歌词)")
            self.status_var.set("无歌词")
        else:
            title = f"{song['name']} — {song['artists']}"
            text = format_lyrics_text(lrc, title)
            self.lyrics_text.insert(tk.END, text)
            self.current_lyrics = lrc
            self.current_title = title
            self.export_btn.configure(state=tk.NORMAL)
            source = lrc.get("source", "auto")
            tag = "API" if source == "api" else "auto romaji"
            self.status_var.set(f"发音来源: {tag}")

        self.lyrics_text.configure(state=tk.DISABLED)

    def _export(self):
        if not self.current_lyrics:
            return
        path = filedialog.asksaveasfilename(
            defaultextension=".md",
            filetypes=[("Markdown", "*.md")],
            initialfile="lyrics.md",
        )
        if not path:
            return
        from lyrics import export_markdown
        title = getattr(self, "current_title", "")
        export_markdown(self.current_lyrics, path, title)
        self.status_var.set(f"已保存: {path}")


def main():
    try:
        root = tk.Tk()
        LyricsApp(root)
        root.mainloop()
    except Exception:
        import traceback
        from pathlib import Path
        log = Path(__file__).with_name("crash.log")
        log.write_text(traceback.format_exc(), encoding="utf-8")
        raise


if __name__ == "__main__":
    main()
