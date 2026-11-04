import os
import subprocess
import sys
from pathlib import Path
from tkinter import messagebox, ttk

from matplotlib.figure import Figure

from src.gui.chart_view import ChartView, ammeter_color
from src.testing.ammeters import AMMETERS
from src.testing.analysis import COMPARISON_COLUMNS, compare_ammeters, comparison_notes
from src.testing.result_store import ResultStore
from src.testing.results import REPORT_COLUMNS, TestRun

RUN_COLUMNS = ("Run ID", "Date", "Status", "Emulators", "Measurements", "Duration (s)", "Frequency (Hz)",
               "Ammeters", "Total time (s)")
DETAIL_COLUMNS = ("Run",) + REPORT_COLUMNS

HINT = "Select one run to see it, or several runs (Ctrl+click or Shift+click) to compare them."


class HistoryTab(ttk.Frame):
    """
    Tab that lists the saved test runs. Selecting one run shows its chart and results,
    selecting several runs compares them.
    """

    def __init__(self, parent, store: ResultStore):
        super().__init__(parent, padding=10)
        self.store = store
        self.columnconfigure(0, weight=1)
        self.rowconfigure(3, weight=1)

        self._build_toolbar()
        self._build_runs_table()
        self.summary = ttk.Label(self, text=HINT, justify="left")
        self.summary.grid(row=2, column=0, sticky="w", pady=(8, 4))

        self.figure = Figure(figsize=(9, 3), dpi=100, layout="constrained")
        self.chart = ChartView(self, self.figure)
        self.chart.widget.grid(row=3, column=0, sticky="nsew")

        self._build_details_table()
        self.refresh()

    # ---------- Layout ----------

    def _build_toolbar(self):
        toolbar = ttk.Frame(self)
        toolbar.grid(row=0, column=0, sticky="ew", pady=(0, 6))
        ttk.Button(toolbar, text="Refresh", command=self.refresh).pack(side="left")
        ttk.Button(toolbar, text="Open folder", command=self._open_folder).pack(side="left", padx=6)
        self.delete_button = ttk.Button(toolbar, text="Delete", command=self._delete, state="disabled")
        self.delete_button.pack(side="left")
        self.status = ttk.Label(toolbar, text="", foreground="gray")
        self.status.pack(side="left", padx=12)

    def _build_runs_table(self):
        frame = ttk.Frame(self)
        frame.grid(row=1, column=0, sticky="ew")
        frame.columnconfigure(0, weight=1)
        self.runs_table = ttk.Treeview(frame, columns=RUN_COLUMNS, show="headings", height=6, selectmode="extended")
        for column in RUN_COLUMNS:
            self.runs_table.heading(column, text=column)
            self.runs_table.column(column, width=90, minwidth=60, anchor="center", stretch=True)
        self.runs_table.column("Run ID", minwidth=150)
        self.runs_table.column("Date", minwidth=130)
        self.runs_table.column("Ammeters", minwidth=180)
        self.runs_table.column("Emulators", minwidth=75)
        self.runs_table.grid(row=0, column=0, sticky="ew")
        scrollbar = ttk.Scrollbar(frame, orient="vertical", command=self.runs_table.yview)
        scrollbar.grid(row=0, column=1, sticky="ns")
        self.runs_table.configure(yscrollcommand=scrollbar.set)
        self.runs_table.bind("<<TreeviewSelect>>", lambda _: self._on_select())

    def _build_details_table(self):
        self.details_tabs = ttk.Notebook(self)
        self.details_tabs.grid(row=4, column=0, sticky="ew", pady=(8, 0))

        frame = ttk.Frame(self.details_tabs, padding=(0, 4, 0, 0))
        frame.columnconfigure(0, weight=1)
        self.details_tabs.add(frame, text="  Results  ")
        self.details_table = _table(frame, DETAIL_COLUMNS, height=5)
        self.details_table.column("Run", minwidth=150)
        self.details_table.column("Max delay (ms)", minwidth=95)
        self.details_table.column("Timing", minwidth=135, width=135)  # e.g. "Late 323/500 (64.6%)"
        self.errors = ttk.Label(frame, text="", foreground="red", justify="left")
        self.errors.grid(row=1, column=0, sticky="w")

        frame = ttk.Frame(self.details_tabs, padding=(0, 4, 0, 0))
        frame.columnconfigure(0, weight=1)
        self.details_tabs.add(frame, text="  Ammeter comparison  ")
        self.comparison_table = _table(frame, COMPARISON_COLUMNS, height=3)
        self.comparison_table.column("Rank", minwidth=45)
        self.comparison_table.column("Success rate", minwidth=130)
        self.comparison_table.column("Run-to-run CV (%)", minwidth=115)
        self.comparison_table.column("95% CI of mean", minwidth=105)
        self.comparison_table.column("Timing", minwidth=255, width=255)  # e.g. "Late in 4 of 5 runs (51.3% of readings)"
        self.comparison_notes = ttk.Label(frame, text="", justify="left", wraplength=1100)
        self.comparison_notes.grid(row=1, column=0, sticky="w", pady=(4, 0))

    # ---------- Runs list ----------

    def refresh(self):
        """
        Reloads the list of saved runs and keeps the current selection if those runs still exist.
        """
        selected = set(self.runs_table.selection())
        self.runs_table.delete(*self.runs_table.get_children())
        runs = self.store.list_runs()
        for run in runs:
            settings = run["settings"]
            self.runs_table.insert("", "end", iid=run["run_id"], values=(
                run["run_id"],
                run["started_at"].replace("T", "  "),
                run["status"].capitalize(),
                run.get("setup", {}).get("emulator_mode", "original").capitalize(),
                settings["count"],
                f"{settings['duration_s']:.6g}",
                f"{settings['frequency_hz']:.6g}",
                ", ".join(result["ammeter"]["name"] for result in run["ammeters"].values()),
                f"{run['total_time_s']:.3f}",
            ))
        self.status.configure(text=f"{len(runs)} saved runs in {self.store.results_dir}")
        still_there = [run_id for run_id in selected if self.runs_table.exists(run_id)]
        if still_there:
            self.runs_table.selection_set(still_there)
        else:
            self._on_select()

    def _on_select(self):
        run_ids = list(self.runs_table.selection())
        self.delete_button.configure(state="normal" if run_ids else "disabled")
        if not run_ids:
            self._show_empty(HINT)
            return
        try:
            runs = sorted((self.store.load(run_id) for run_id in run_ids), key=lambda run: run.run_id)
        except (OSError, ValueError) as error:
            self._show_empty(f"Could not open the run: {error}")
            return
        if len(runs) == 1:
            self._show_run(runs[0])
        else:
            self._show_comparison(runs)

    # ---------- Showing runs ----------

    def _show_empty(self, message: str):
        self.summary.configure(text=message)
        self.details_table.delete(*self.details_table.get_children())
        self.errors.configure(text="")
        self.comparison_table.delete(*self.comparison_table.get_children())
        self.comparison_notes.configure(text="")
        self.figure.clear()
        self.chart.draw()

    def _fill_details(self, runs: list):
        self.comparison_table.delete(*self.comparison_table.get_children())
        comparisons = compare_ammeters(runs)
        for comparison in comparisons:
            row = comparison.report_row()
            self.comparison_table.insert("", "end", values=[row[column] for column in COMPARISON_COLUMNS])
        self.comparison_notes.configure(text="\n".join(comparison_notes(comparisons)))

        self.details_table.delete(*self.details_table.get_children())
        errors = []
        for run in runs:
            for row in run.report_rows():
                self.details_table.insert("", "end", values=[run.run_id] + [row[column] for column in REPORT_COLUMNS])
            errors += [f"{run.run_id}  {error}" for error in run.errors()]
        shown = errors[:3]
        if len(errors) > len(shown):
            shown.append(f"... and {len(errors) - len(shown)} more errors")
        self.errors.configure(text="\n".join(shown))

    def _show_run(self, run: TestRun):
        """
        Shows one run: its readings over time and its results, as when it ran.
        """
        constants = ", ".join(f"{AMMETERS[ammeter_type].name if ammeter_type in AMMETERS else ammeter_type} "
                              f"{name} = {value:.6g}"
                              for ammeter_type, values in run.setup.get("device_constants", {}).items()
                              for name, value in values.items())
        self.summary.configure(text=f"Run {run.run_id}, started {run.started_at:%Y-%m-%d %H:%M:%S}, "
                                    f"{run.emulator_mode} emulators" + (f" ({constants})" if constants else "") +
                                    f"\n{run.summary()}")
        self._fill_details([run])

        self.figure.clear()
        first_axis = None
        for index, (ammeter_type, result) in enumerate(run.results.items()):
            axis = self.figure.add_subplot(len(run.results), 1, index + 1, sharex=first_axis)
            first_axis = first_axis or axis
            times = [seconds for seconds, _ in result.readings]
            axis.plot(times, result.currents, ".-", color=ammeter_color(ammeter_type))
            axis.set_title(f"{result.ammeter.name}  -  {result.ammeter.method}", fontsize=10, loc="left")
            axis.set_ylabel("Current (A)")
            axis.set_xlim(0, run.settings.duration)
            axis.grid(True, alpha=0.3)
            if index < len(run.results) - 1:
                axis.tick_params(labelbottom=False)
        if first_axis:
            axis.set_xlabel("Time (s)")
        self.chart.draw()

    def _show_comparison(self, runs: list):
        """
        Compares several runs: one box plot per ammeter, with one box per run,
        showing how the measured current spread in each run.
        """
        same_settings = len({run.settings for run in runs}) == 1
        note = "All runs used the same settings." if same_settings else \
            "Note: the runs used different settings (see the list above)."
        if len({run.emulator_mode for run in runs}) > 1:
            note += " Warning: the runs used different emulator modes (original and realistic), " \
                    "so their results are not directly comparable."
        self.summary.configure(text=f"Comparing {len(runs)} runs, oldest first. {note}\n"
                                    f"Each box shows the spread of the current in one run: the line is the median, "
                                    f"the triangle is the mean.")
        self._fill_details(runs)

        # Ammeter types in any of the runs, in the usual order
        types = [t for t in AMMETERS if any(t in run.results for run in runs)]
        types += [t for run in runs for t in run.results if t not in types]
        labels = [f"{run.started_at:%d/%m %H:%M:%S}" for run in runs]

        self.figure.clear()
        for index, ammeter_type in enumerate(types):
            axis = self.figure.add_subplot(len(types), 1, index + 1)
            data = [(position, run.results[ammeter_type].currents) for position, run in enumerate(runs, start=1)
                    if ammeter_type in run.results and run.results[ammeter_type].currents]
            if data:
                color = ammeter_color(ammeter_type)
                axis.boxplot([currents for _, currents in data], positions=[position for position, _ in data],
                             widths=0.5, patch_artist=True, showmeans=True,
                             boxprops={"facecolor": color, "alpha": 0.35}, medianprops={"color": "black"},
                             meanprops={"markerfacecolor": color, "markeredgecolor": "black"})
            for position, run in enumerate(runs, start=1):
                if ammeter_type not in run.results:
                    axis.text(position, 0.5, "not tested", transform=axis.get_xaxis_transform(),
                              ha="center", va="center", color="gray", fontsize=9)
            name = next(run.results[ammeter_type].ammeter.name for run in runs if ammeter_type in run.results)
            axis.set_title(name, fontsize=10, loc="left")
            axis.set_ylabel("Current (A)")
            axis.set_xlim(0.5, len(runs) + 0.5)
            axis.set_xticks(range(1, len(runs) + 1))
            axis.grid(True, axis="y", alpha=0.3)
            if index < len(types) - 1:
                axis.tick_params(labelbottom=False)
            else:
                axis.set_xticklabels(labels, rotation=20 if len(runs) > 6 else 0, fontsize=8)
                axis.set_xlabel("Test run (start time)")
        self.chart.draw()

    # ---------- Buttons ----------

    def _open_folder(self):
        """
        Opens the selected run's folder, or the results folder, in the file manager.
        """
        run_ids = self.runs_table.selection()
        folder = self.store.runs_dir / run_ids[0] if len(run_ids) == 1 else self.store.results_dir
        folder.mkdir(parents=True, exist_ok=True)
        try:
            _open_in_file_manager(folder)
        except OSError as error:
            messagebox.showerror("Open folder", f"Could not open {folder}:\n{error}")

    def _delete(self):
        run_ids = list(self.runs_table.selection())
        if not run_ids:
            return
        question = f"Delete {len(run_ids)} saved runs?" if len(run_ids) > 1 else f"Delete the run {run_ids[0]}?"
        if not messagebox.askyesno("Delete", f"{question}\nThis can't be undone."):
            return
        for run_id in run_ids:
            try:
                self.store.delete(run_id)
            except (OSError, ValueError) as error:
                messagebox.showerror("Delete", f"Could not delete {run_id}:\n{error}")
        self.runs_table.selection_set([])
        self.refresh()


def _table(parent, columns: tuple, height: int) -> ttk.Treeview:
    """
    Creates a table with a vertical scroll bar in row 0 of `parent`.
    """
    table = ttk.Treeview(parent, columns=columns, show="headings", height=height)
    for column in columns:
        table.heading(column, text=column)
        table.column(column, width=60, minwidth=60, anchor="center", stretch=True)
    table.grid(row=0, column=0, sticky="ew")
    scrollbar = ttk.Scrollbar(parent, orient="vertical", command=table.yview)
    scrollbar.grid(row=0, column=1, sticky="ns")
    table.configure(yscrollcommand=scrollbar.set)
    return table


def _open_in_file_manager(folder: Path):
    if sys.platform == "win32":
        os.startfile(folder)
    elif sys.platform == "darwin":
        subprocess.run(["open", str(folder)], check=False)
    else:
        subprocess.run(["xdg-open", str(folder)], check=False)
