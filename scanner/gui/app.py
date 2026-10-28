"""Main window for Resume Scanner & Ranker.

P6: connects the GUI to the pipeline via a background worker thread and a
queue.Queue. Only the Tkinter main thread touches widgets; the worker
posts Progress / Finished / Failed / Cancelled messages which the GUI
polls with root.after(QUEUE_POLL_MS).

P5 behaviors (JD Clear/Load .txt, Add Files/Add Folder/Remove/Clear all,
counter, status bar) are retained.
"""

from __future__ import annotations

import csv
import logging
import os
import queue
import threading
from pathlib import Path
from tkinter import filedialog, messagebox, scrolledtext
from tkinter import ttk

import tkinter as tk

from scanner.config import APP_NAME, MAX_RESUMES, QUEUE_POLL_MS, SUPPORTED_EXTENSIONS
from scanner.errors import InvalidJobDescriptionError
from scanner.gui.worker import Cancelled, Finished, Failed, Progress, ScanWorker
from scanner.pipeline import scan_and_rank
from scanner.preprocess import normalize_text
from scanner.exporter import export_csv


class MainWindow:
    """Top-level application window."""

    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title(APP_NAME)
        self.root.minsize(900, 650)
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)

        # Threading state.
        self.out_queue: "queue.Queue[Progress | Finished | Failed | Cancelled]" = (
            queue.Queue()
        )
        self.cancel_event = threading.Event()
        self.worker: ScanWorker | None = None
        self.report = None  # type: ignore[assignment]

        self.resume_paths: list[str] = []

        self._build_layout()
        self._start_polling()
        self._set_status("Ready. Paste a JD and add resumes, then click Scan & Rank.")

        # Cancel any running scan when the window is closed.
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    # ------------------------------------------------------------------ #
    # Layout
    # ------------------------------------------------------------------ #
    def _build_layout(self) -> None:
        container = ttk.Frame(self.root, padding=10)
        container.grid(row=0, column=0, sticky="nsew")
        container.columnconfigure(0, weight=1)

        container.rowconfigure(0, weight=0)  # JD
        container.rowconfigure(1, weight=0)  # Resumes header
        container.rowconfigure(2, weight=1)  # Resumes list
        container.rowconfigure(3, weight=0)  # Controls
        container.rowconfigure(4, weight=1)  # Results notebook
        container.rowconfigure(5, weight=0)  # Status bar

        self._build_jd_section(container, row=0)
        self._build_resumes_section(container, row=1)
        self._build_resumes_list(container, row=2)
        self._build_controls(container, row=3)
        self._build_results(container, row=4)
        self._build_status(container, row=5)

    def _build_jd_section(self, parent: ttk.Frame, row: int) -> None:
        frame = ttk.LabelFrame(parent, text="Job Description", padding=8)
        frame.grid(row=row, column=0, sticky="nsew", pady=(0, 8))
        frame.columnconfigure(0, weight=1)

        btns = ttk.Frame(frame)
        btns.grid(row=0, column=0, sticky="ew", pady=(0, 6))
        ttk.Button(btns, text="Load .txt", command=self._load_jd).pack(side="left")
        ttk.Button(btns, text="Clear", command=self._clear_jd).pack(side="left", padx=(6, 0))

        self.jd_text = scrolledtext.ScrolledText(frame, height=6, wrap=tk.WORD)
        self.jd_text.grid(row=1, column=0, sticky="nsew")
        frame.rowconfigure(1, weight=1)

    def _build_resumes_section(self, parent: ttk.Frame, row: int) -> None:
        frame = ttk.Frame(parent)
        frame.grid(row=row, column=0, sticky="ew", pady=(0, 4))
        frame.columnconfigure(0, weight=1)

        self.resumes_label = ttk.Label(frame, text="Resumes (0)")
        self.resumes_label.grid(row=0, column=0, sticky="w")

        btns = ttk.Frame(frame)
        btns.grid(row=0, column=1, sticky="e")
        self.add_files_btn = ttk.Button(btns, text="Add Files", command=self._add_files)
        self.add_files_btn.pack(side="left")
        self.add_folder_btn = ttk.Button(btns, text="Add Folder", command=self._add_folder)
        self.add_folder_btn.pack(side="left", padx=(4, 0))
        self.remove_btn = ttk.Button(btns, text="Remove", command=self._remove_selected)
        self.remove_btn.pack(side="left", padx=(4, 0))
        self.clear_all_btn = ttk.Button(btns, text="Clear all", command=self._clear_all)
        self.clear_all_btn.pack(side="left", padx=(4, 0))

    def _build_resumes_list(self, parent: ttk.Frame, row: int) -> None:
        frame = ttk.Frame(parent)
        frame.grid(row=row, column=0, sticky="nsew", pady=(0, 8))
        frame.columnconfigure(0, weight=1)
        frame.rowconfigure(0, weight=1)

        self.resumes_list = tk.Listbox(frame, selectmode=tk.EXTENDED, height=8)
        self.resumes_list.grid(row=0, column=0, sticky="nsew")

        scroll = ttk.Scrollbar(frame, orient="vertical", command=self.resumes_list.yview)
        scroll.grid(row=0, column=1, sticky="ns")
        self.resumes_list.configure(yscrollcommand=scroll.set)

    def _build_controls(self, parent: ttk.Frame, row: int) -> None:
        frame = ttk.Frame(parent)
        frame.grid(row=row, column=0, sticky="ew", pady=(0, 8))
        frame.columnconfigure(3, weight=1)

        self.scan_btn = ttk.Button(frame, text="Scan & Rank", command=self._scan, state="disabled")
        self.scan_btn.grid(row=0, column=0)

        self.cancel_btn = ttk.Button(frame, text="Cancel", command=self._cancel, state="disabled")
        self.cancel_btn.grid(row=0, column=1, padx=(6, 0))

        self.progress = ttk.Progressbar(frame, mode="determinate", length=200)
        self.progress.grid(row=0, column=2, padx=(12, 0), sticky="e")

        self.progress_label = ttk.Label(frame, text="0 / 0")
        self.progress_label.grid(row=0, column=3, padx=(6, 0), sticky="e")

        self.export_btn = ttk.Button(frame, text="Export CSV", command=self._export_csv, state="disabled")
        self.export_btn.grid(row=0, column=4, padx=(12, 0))

    def _build_results(self, parent: ttk.Frame, row: int) -> None:
        frame = ttk.Frame(parent)
        frame.grid(row=row, column=0, sticky="nsew")
        frame.columnconfigure(0, weight=1)
        frame.rowconfigure(0, weight=1)

        self.notebook = ttk.Notebook(frame)
        self.notebook.grid(row=0, column=0, sticky="nsew")

        # Ranking tab.
        self.ranking_frame = ttk.Frame(self.notebook, padding=6)
        self.notebook.add(self.ranking_frame, text="Ranking")

        cols = ("rank", "file", "match", "level", "terms")
        self.ranking_tree = ttk.Treeview(
            self.ranking_frame, columns=cols, show="headings", height=10
        )
        self.ranking_tree.heading("rank", text="Rank", command=lambda: self._sort_tree("rank"))
        self.ranking_tree.heading("file", text="File", command=lambda: self._sort_tree("file"))
        self.ranking_tree.heading("match", text="Match %", command=lambda: self._sort_tree("match"))
        self.ranking_tree.heading("level", text="Level", command=lambda: self._sort_tree("level"))
        self.ranking_tree.heading("terms", text="Top keywords", command=lambda: self._sort_tree("terms"))
        self.ranking_tree.column("rank", width=50, anchor="center")
        self.ranking_tree.column("file", width=180)
        self.ranking_tree.column("match", width=80, anchor="center")
        self.ranking_tree.column("level", width=90, anchor="center")
        self.ranking_tree.column("terms", width=300)
        self.ranking_tree.grid(row=0, column=0, sticky="nsew")
        self.ranking_frame.columnconfigure(0, weight=1)
        self.ranking_frame.rowconfigure(0, weight=1)

        rank_scroll = ttk.Scrollbar(
            self.ranking_frame, orient="vertical", command=self.ranking_tree.yview
        )
        rank_scroll.grid(row=0, column=1, sticky="ns")
        self.ranking_tree.configure(yscrollcommand=rank_scroll.set)

        # Level color tags.
        self.ranking_tree.tag_configure("Excellent", foreground="#1e7a1e")
        self.ranking_tree.tag_configure("Good", foreground="#2e7d32")
        self.ranking_tree.tag_configure("Fair", foreground="#b26a00")
        self.ranking_tree.tag_configure("Low", foreground="#888888")

        # Skipped tab.
        self.skipped_frame = ttk.Frame(self.notebook, padding=6)
        self.notebook.add(self.skipped_frame, text="Skipped (0)")

        skipped_cols = ("file", "reason")
        self.skipped_tree = ttk.Treeview(
            self.skipped_frame, columns=skipped_cols, show="headings", height=6
        )
        self.skipped_tree.heading("file", text="File")
        self.skipped_tree.heading("reason", text="Reason")
        self.skipped_tree.column("file", width=200)
        self.skipped_tree.column("reason", width=400)
        self.skipped_tree.grid(row=0, column=0, sticky="nsew")
        self.skipped_frame.columnconfigure(0, weight=1)
        self.skipped_frame.rowconfigure(0, weight=1)

        skipped_scroll = ttk.Scrollbar(
            self.skipped_frame, orient="vertical", command=self.skipped_tree.yview
        )
        skipped_scroll.grid(row=0, column=1, sticky="ns")
        self.skipped_tree.configure(yscrollcommand=skipped_scroll.set)

        # Detail label.
        self.detail_label = ttk.Label(
            frame,
            text="Select a ranked row to see full path and top terms.",
            wraplength=900,
        )
        self.detail_label.grid(row=1, column=0, sticky="ew", pady=(6, 0))

        # Row selection -> detail.
        self.ranking_tree.bind("<<TreeviewSelect>>", self._on_rank_select)

    def _build_status(self, parent: ttk.Frame, row: int) -> None:
        self.status = ttk.Label(parent, text="", relief="sunken", anchor="w")
        self.status.grid(row=row, column=0, sticky="ew")

    # ------------------------------------------------------------------ #
    # Polling (main thread only)
    # ------------------------------------------------------------------ #
    def _start_polling(self) -> None:
        self.root.after(QUEUE_POLL_MS, self._poll_queue)

    def _poll_queue(self) -> None:
        """Drain the queue and update widgets. Runs on the main thread."""
        try:
            while True:
                msg = self.out_queue.get_nowait()
                self._handle_message(msg)
        except queue.Empty:
            pass

        # Reschedule. If a worker is alive, keep polling; otherwise we can
        # still keep polling so a future scan's messages get delivered.
        self.root.after(QUEUE_POLL_MS, self._poll_queue)

    def _handle_message(self, msg) -> None:
        if isinstance(msg, Progress):
            self.progress["maximum"] = msg.total
            self.progress["value"] = msg.done
            self.progress_label.config(text=f"{msg.done} / {msg.total}")
            self._set_status(f"Scanning: {msg.name}")
        elif isinstance(msg, Finished):
            self._scan_finished(msg.report)
        elif isinstance(msg, Failed):
            self._scan_failed(msg.message)
        elif isinstance(msg, Cancelled):
            self._scan_cancelled()

    # ------------------------------------------------------------------ #
    # Status helpers
    # ------------------------------------------------------------------ #
    def _set_status(self, message: str) -> None:
        self.status.config(text=message)

    def _update_counter(self) -> None:
        self.resumes_label.config(text=f"Resumes ({len(self.resume_paths)})")
        self._refresh_scan_state()

    def _refresh_scan_state(self) -> None:
        enabled = len(self.resume_paths) > 0 and self.worker is None
        self.scan_btn.config(state="normal" if enabled else "disabled")

    # ------------------------------------------------------------------ #
    # Scan / cancel / export
    # ------------------------------------------------------------------ #
    def _scan(self) -> None:
        jd = self.jd_text.get("1.0", tk.END).strip()
        if len(normalize_text(jd)) < 20:
            messagebox.showerror(
                "Invalid JD",
                "Job description has no meaningful keywords. "
                "Add some keywords and try again.",
            )
            return
        if not self.resume_paths:
            messagebox.showerror("No resumes", "Add at least one resume.")
            return

        # Reset UI.
        self.cancel_event.clear()
        self.ranking_tree.delete(*self.ranking_tree.get_children())
        self.skipped_tree.delete(*self.skipped_tree.get_children())
        self.notebook.tab(self.skipped_frame, text="Skipped (0)")
        self.detail_label.config(text="Select a ranked row to see full path and top terms.")
        self.progress["value"] = 0
        self.progress_label.config(text="0 / 0")

        # Button states: scanning.
        self.scan_btn.config(state="disabled")
        self.cancel_btn.config(state="normal")
        self.add_files_btn.config(state="disabled")
        self.add_folder_btn.config(state="disabled")
        self.remove_btn.config(state="disabled")
        self.clear_all_btn.config(state="disabled")
        self.export_btn.config(state="disabled")

        self.worker = ScanWorker(
            jd=jd,
            paths=[Path(p) for p in self.resume_paths],
            out_queue=self.out_queue,
            cancel_event=self.cancel_event,
        )
        self.worker.start()
        self._set_status("Scan started...")

    def _cancel(self) -> None:
        self.cancel_event.set()
        self._set_status("Cancelling...")

    def _export_csv(self) -> None:
        if self.report is None:
            return
        dest = filedialog.asksaveasfilename(
            title="Export ranking to CSV",
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
        )
        if not dest:
            return
        try:
            export_csv(self.report, dest)
            self._set_status(f"Exported to {os.path.basename(dest)}")
        except Exception as exc:  # noqa: BLE001
            logging.exception("Export failed")
            messagebox.showerror("Export error", str(exc))

    # ------------------------------------------------------------------ #
    # Message handlers (main thread)
    # ------------------------------------------------------------------ #
    def _scan_finished(self, report) -> None:
        self.report = report
        self.cancel_event.clear()
        self.worker = None

        # Ranking tab.
        self.ranking_tree.delete(*self.ranking_tree.get_children())
        for row in report.ranked:
            self.ranking_tree.insert(
                "",
                "end",
                values=(
                    row.rank,
                    row.path.name,
                    f"{row.percent:.1f}",
                    row.level.value,
                    ", ".join(row.top_terms),
                ),
                tags=(row.level.value,),
            )

        # Skipped tab.
        self.skipped_tree.delete(*self.skipped_tree.get_children())
        for failure in report.failures:
            self.skipped_tree.insert(
                "", "end", values=(failure.path.name, failure.reason)
            )
        self.notebook.tab(
            self.skipped_frame, text=f"Skipped ({len(report.failures)})"
        )

        self._set_status(
            f"Done. {len(report.ranked)} ranked, {len(report.failures)} skipped."
        )
        self._restore_buttons()
        self.export_btn.config(state="normal" if report.ranked else "disabled")

    def _scan_failed(self, message: str) -> None:
        self.cancel_event.clear()
        self.worker = None
        self._set_status("Scan failed.")
        self._restore_buttons()
        messagebox.showerror("Scan error", message)

    def _scan_cancelled(self) -> None:
        self.cancel_event.clear()
        self.worker = None
        self._set_status("Scan cancelled.")
        self._restore_buttons()
        self.progress["value"] = 0
        self.progress_label.config(text="0 / 0")

    def _restore_buttons(self) -> None:
        """Re-enable UI controls after a scan finishes/cancels/fails."""
        self.scan_btn.config(state="normal" if self.resume_paths else "disabled")
        self.cancel_btn.config(state="disabled")
        self.add_files_btn.config(state="normal")
        self.add_folder_btn.config(state="normal")
        self.remove_btn.config(state="normal")
        self.clear_all_btn.config(state="normal")

    # ------------------------------------------------------------------ #
    # JD actions
    # ------------------------------------------------------------------ #
    def _load_jd(self) -> None:
        path = filedialog.askopenfilename(
            title="Load job description",
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")],
        )
        if not path:
            return
        try:
            with open(path, "r", encoding="utf-8-sig") as fh:
                content = fh.read()
        except UnicodeDecodeError:
            try:
                with open(path, "r", encoding="cp1252") as fh:
                    content = fh.read()
            except Exception as exc:  # noqa: BLE001
                messagebox.showerror("Load error", f"Could not read file: {exc}")
                return
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror("Load error", f"Could not read file: {exc}")
            return
        self.jd_text.delete("1.0", tk.END)
        self.jd_text.insert(tk.END, content)
        self._set_status(f"Loaded JD from {os.path.basename(path)}")

    def _clear_jd(self) -> None:
        self.jd_text.delete("1.0", tk.END)
        self._set_status("JD cleared.")

    # ------------------------------------------------------------------ #
    # Resume list actions
    # ------------------------------------------------------------------ #
    def _add_files(self) -> None:
        paths = filedialog.askopenfilenames(
            title="Add resumes",
            filetypes=[
                ("Supported files", "".join(f"*{ext}" for ext in sorted(SUPPORTED_EXTENSIONS))),
                ("PDF files", "*.pdf"),
                ("Word files", "*.docx"),
                ("Text files", "*.txt"),
                ("All files", "*.*"),
            ],
        )
        for path in paths:
            self._add_path(path)

    def _add_folder(self) -> None:
        folder = filedialog.askdirectory(title="Add resumes from folder")
        if not folder:
            return
        for name in sorted(os.listdir(folder)):
            full = os.path.join(folder, name)
            if os.path.isfile(full):
                self._add_path(full)

    def _add_path(self, path: str) -> None:
        ext = os.path.splitext(path)[1].lower()
        if ext not in SUPPORTED_EXTENSIONS:
            messagebox.showinfo(
                "Ignored",
                f"Unsupported file type: {ext or 'no extension'}",
            )
            return
        if path in self.resume_paths:
            return
        if len(self.resume_paths) >= MAX_RESUMES:
            messagebox.showwarning(
                "Limit reached",
                f"Maximum of {MAX_RESUMES} resumes reached. "
                f"Remove some files before adding more.",
            )
            return
        self.resume_paths.append(path)
        self.resumes_list.insert(tk.END, path)
        self._update_counter()
        self._set_status(f"Added {os.path.basename(path)}")

    def _remove_selected(self) -> None:
        selection = self.resumes_list.curselection()
        if not selection:
            return
        for index in reversed(selection):
            self.resumes_list.delete(index)
            del self.resume_paths[index]
        self._update_counter()
        self._set_status(f"Removed {len(selection)} file(s).")

    def _clear_all(self) -> None:
        self.resumes_list.delete(0, tk.END)
        self.resume_paths.clear()
        self._update_counter()
        self._set_status("Cleared all resumes.")

    # ------------------------------------------------------------------ #
    # Ranking table: sort + detail
    # ------------------------------------------------------------------ #
    def _sort_tree(self, col: str) -> None:
        """Sort the Ranking treeview by the clicked column."""
        data = [
            (self.ranking_tree.set(child, col), child)
            for child in self.ranking_tree.get_children("")
        ]
        # Try numeric sort for match/rank, else string.
        def _key(item):
            val = item[0]
            try:
                return float(val), ""
            except ValueError:
                return 0.0, val.lower()

        data.sort(key=_key)
        for index, (_, child) in enumerate(data):
            self.ranking_tree.move(child, "", index)

    def _on_rank_select(self, _event) -> None:
        selection = self.ranking_tree.selection()
        if not selection:
            return
        item = selection[0]
        values = self.ranking_tree.item(item, "values")
        if not values:
            return
        rank, file_name, match, level, terms = values
        # Find the full path from the report.
        full_path = ""
        top_terms = ""
        if self.report is not None:
            for row in self.report.ranked:
                if row.path.name == file_name and row.rank == int(rank):
                    full_path = str(row.path)
                    top_terms = ", ".join(row.top_terms)
                    break
        self.detail_label.config(
            text=f"Rank {rank} — {file_name}\n"
                 f"Full path: {full_path}\n"
                 f"Match: {match}%  Level: {level}\n"
                 f"Top terms: {top_terms}"
        )

    # ------------------------------------------------------------------ #
    # Window close
    # ------------------------------------------------------------------ #
    def _on_close(self) -> None:
        if self.worker is not None and self.worker.is_alive():
            self.cancel_event.set()
        self.root.destroy()


def main() -> None:
    """Entry point: build Tk root, MainWindow, run mainloop."""
    root = tk.Tk()
    MainWindow(root)
    root.mainloop()
