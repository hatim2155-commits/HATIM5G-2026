from __future__ import annotations

import argparse
import sys
import tkinter as tk
from tkinter import ttk

from core.huawei import HuaweiRouter
from core.i18n import LANGUAGES, current_language, set_language, t

APP_NAME = "HATIM5G"


def parse_args(argv: list[str] | None = None):
    p = argparse.ArgumentParser(description=f"{APP_NAME} — Arabic antenna monitor prototype")
    p.add_argument("--lang", choices=list(LANGUAGES.keys()), default="ar", help="Language code")
    p.add_argument("--ip", default="demo", help="Router IP or demo")
    return p.parse_args(argv)


class App:
    def __init__(self, root: tk.Tk, ip: str) -> None:
        self.root = root
        self.root.title(APP_NAME)
        self.router = HuaweiRouter(ip)
        self.build_ui()

    def build_ui(self) -> None:
        top = ttk.Frame(self.root, padding=10)
        top.pack(fill=tk.X)

        self.status_lbl = ttk.Label(top, text=t("غير متصل"), foreground="red", font=("Segoe UI", 12, "bold"))
        self.status_lbl.pack(side=tk.LEFT)

        self.lang_var = tk.StringVar(value=LANGUAGES.get(current_language(), "العربية"))
        lang_cb = ttk.Combobox(top, textvariable=self.lang_var, values=list(LANGUAGES.values()), state="readonly", width=12)
        lang_cb.pack(side=tk.RIGHT)
        ttk.Label(top, text=t("اللغة:")).pack(side=tk.RIGHT)
        lang_cb.bind("<<ComboboxSelected>>", self.on_lang_change)

        en_btn = ttk.Button(top, text="en", width=3, command=self.set_en)
        en_btn.pack(side=tk.RIGHT, padx=(4, 0))

        body = ttk.Frame(self.root, padding=10)
        body.pack(fill=tk.BOTH, expand=True)

        # ip row
        row = ttk.Frame(body)
        row.pack(fill=tk.X, pady=(0, 8))
        ttk.Label(row, text="IP:").pack(side=tk.LEFT, padx=(0, 6))
        self.ip_var = tk.StringVar(value=self.router.ip)
        ttk.Entry(row, textvariable=self.ip_var, width=18).pack(side=tk.LEFT)

        btn_row = ttk.Frame(body)
        btn_row.pack(fill=tk.X, pady=(0, 8))
        ttk.Button(btn_row, text=t("🚀 اتصال"), command=self.connect).pack(side=tk.LEFT, padx=(0, 8))
        ttk.Button(btn_row, text=t("📶 فحص الإشارة"), command=self.scan_signal).pack(side=tk.LEFT, padx=(0, 8))
        ttk.Button(btn_row, text=t("🔒 تطبيق Band Lock"), command=self.apply_band_lock).pack(side=tk.LEFT, padx=(0, 8))
        ttk.Button(btn_row, text=t("↩ استرجاع"), command=self.restore).pack(side=tk.LEFT)

        self.info = ttk.Label(body, text=t("جارٍ البحث عن الراوتر..."), justify="left", wraplength=500)
        self.info.pack(anchor=tk.W, pady=(0, 8))

        self.warning = ttk.Label(body, text="", foreground="firebrick", justify="left", wraplength=520)
        self.warning.pack(anchor=tk.W)

        self.result = ttk.Label(body, text="", justify="left", wraplength=520, font=("Segoe UI", 10, "bold"))
        self.result.pack(anchor=tk.W, pady=(10, 0))

    def on_lang_change(self, event=None) -> None:
        selected = self.lang_var.get()
        for code, label in LANGUAGES.items():
            if label == selected:
                set_language(code)
                break
        self.root.destroy()
        main(["--lang", current_language(), "--ip", self.ip_var.get()])

    def set_en(self) -> None:
        set_language("en")
        self.root.destroy()
        main(["--lang", "en", "--ip", self.ip_var.get()])

    def connect(self) -> None:
        self.router = HuaweiRouter(self.ip_var.get())
        status = self.router.connect()
        self.status_lbl.config(text=t("متصل"), foreground="green")
        self.info.config(text=f"{status.model} | IP: {status.ip} | band: {status.band} | signal: {status.signal_dbm} dBm")
        if not status.supported_band_lock:
            self.warning.config(text=t("هذا الراوتر مقيد — تعديل النطاقات غير متاح."))
        else:
            self.warning.config(text="")

    def scan_signal(self) -> None:
        status = self.router.read_status()
        best_band, best_signal = self.router.scan_best_signal()
        self.status_lbl.config(text=t("متصل"), foreground="green")
        self.result.config(text=f"أفضل إشارة: {best_band} | {best_signal} dBm | الإشارة الحالية: {status.signal_dbm} dBm")
        self.info.config(text=f"{status.provider} / {status.model} / {status.ip}")

    def apply_band_lock(self) -> None:
        try:
            selected = [3, 7, 20]
            status = self.router.apply_band_lock(selected)
            self.result.config(text=f"{t('Band Lock применён: {bands}.').format(bands=', '.join(f'B{b}' for b in selected))}")
            self.warning.config(text="")
            self.info.config(text=f"{status.model} | {status.band} | {status.signal_dbm} dBm")
        except ValueError as exc:
            self.warning.config(text=str(exc))
            self.result.config(text="")

    def restore(self) -> None:
        status = self.router.restore_original()
        self.result.config(text=f"تمت استعادة الإعدادات الأصلية | {status.band}")
        self.warning.config(text="")


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    set_language(args.lang)
    root = tk.Tk()
    app = App(root, args.ip)
    try:
        root.mainloop()
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
