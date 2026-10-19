#!/usr/bin/env python3
"""
Minimal launcher prototype for HATIM5G. This is an early stable scaffold:
- sets APP_NAME to HATIM5G
- uses core.i18n for language selection (ru/en/ar)
- creates a tiny Tk UI demonstrating language switch

Next: integrate the full Hua4GMon core logic and UI components and translate all strings.
"""
from __future__ import annotations

import argparse
import sys
import tkinter as tk
from tkinter import ttk

from core.i18n import t, set_language, LANGUAGES, current_language

APP_NAME = "HATIM5G"


def parse_args(argv: list[str] | None = None):
    p = argparse.ArgumentParser(description=f"{APP_NAME} — Arabic UI antenna monitor (prototype)")
    p.add_argument('--lang', choices=list(LANGUAGES.keys()), default='ar', help='Language code (ru/en/ar)')
    return p.parse_args(argv)


class App:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title(f"{APP_NAME}")
        self.build_ui()

    def build_ui(self):
        top = ttk.Frame(self.root, padding=10)
        top.pack(fill=tk.X)

        self.status_lbl = ttk.Label(top, text=t("Отключено"), foreground='red', font=('Segoe UI', 12, 'bold'))
        self.status_lbl.pack(side=tk.LEFT)

        # language selection combobox
        lang_var = tk.StringVar(value=LANGUAGES.get(current_language(), 'Русский'))
        self.lang_map = {name: code for code, name in LANGUAGES.items()}
        cb = ttk.Combobox(top, textvariable=lang_var, values=list(LANGUAGES.values()), state='readonly', width=12)
        cb.pack(side=tk.RIGHT)
        ttk.Label(top, text=t("Язык:")).pack(side=tk.RIGHT)
        cb.bind('<<ComboboxSelected>>', lambda e: self.on_lang_change(cb.get()))

        body = ttk.Frame(self.root, padding=10)
        body.pack(fill=tk.BOTH, expand=True)

        ttk.Button(body, text=t("🚀 Подключиться"), command=self.connect).pack(pady=6)
        ttk.Button(body, text=t("⏹ Отключиться"), command=self.disconnect).pack(pady=6)

        self.info = ttk.Label(body, text=t("Ищу роутер…"))
        self.info.pack(pady=6)

    def on_lang_change(self, name: str):
        # name is human readable; find code
        for code, label in LANGUAGES.items():
            if label == name:
                set_language(code)
                break
        # rebuild UI to apply translations (simple approach)
        self.root.destroy()
        main()

    def connect(self):
        self.status_lbl.config(text=t("Подключение..."), foreground='orange')
        self.info.config(text=t("Найден роутер {model} на {ip}").format(model='Huawei B618', ip='192.168.8.1'))

    def disconnect(self):
        self.status_lbl.config(text=t("Отключено"), foreground='red')
        self.info.config(text=t("Роутер не найден. Проверьте подключение к его Wi-Fi/USB."))


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    set_language(args.lang)

    root = tk.Tk()
    app = App(root)
    try:
        root.mainloop()
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == '__main__':
    sys.exit(main())
