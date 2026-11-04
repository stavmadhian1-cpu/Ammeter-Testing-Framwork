import statistics
import tkinter as tk
from tkinter import font as tkfont
from tkinter import ttk

from matplotlib.colors import to_hex
from matplotlib.figure import Figure

from src.gui.chart_view import ChartView, ammeter_color
from src.testing.analysis import assess_ammeters, assessment_notes, timing_note
from src.testing.result_store import ResultStore

MODE_FILTERS = {"All runs": None, "Original emulators": "original", "Realistic emulators": "realistic"}
CHECKED, UNCHECKED = "☑", "☐"
UPDATE_DELAY_MS = 250  # Wait a moment after a click, so ticking several runs quickly updates the analysis once


class AnalysisTab(ttk.Frame):
    """
    Tab that compares the ammeter types over the runs the user picks (Accuracy Assessment):
    a verdict, one card per ammeter with its statistics, four charts and notes.
    """

    def __init__(self, parent, store: ResultStore):
        super().__init__(parent, padding=10)
        self.store = store
        self.checked = set()   # IDs of the ticked runs
        self.run_info = {}     # Run ID -> saved data, for the runs in the list
        self.loaded = {}       # Run ID -> TestRun, so each run is loaded from its files only once
        self.pending_update = None
        self.columnconfigure(1, weight=1)
        self.rowconfigure(0, weight=1)

        self._build_picker()
        self._build_content()
        self.refresh()

    # ---------- Layout ----------

    def _build_picker(self):
        panel = ttk.LabelFrame(self, text="Runs to compare", padding=8)
        panel.grid(row=0, column=0, sticky="ns", padx=(0, 10))
        panel.rowconfigure(1, weight=1)

        top = ttk.Frame(panel)
        top.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 6))
        ttk.Label(top, text="Show:").pack(side="left")
        self.mode_filter = ttk.Combobox(top, values=list(MODE_FILTERS), state="readonly", width=20)
        self.mode_filter.set("All runs")
        self.mode_filter.pack(side="left", padx=6)
        self.mode_filter.bind("<<ComboboxSelected>>", lambda _: self.refresh())

        columns = ("check", "started", "mode", "count", "frequency", "ammeters", "timing")
        self.runs_list = ttk.Treeview(panel, columns=columns, show="headings", selectmode="none", height=20)
        for column, heading, width in zip(columns, ("", "Started", "Mode", "Meas.", "Hz", "Ammeters", "Timing"),
                                          (28, 112, 70, 48, 48, 62, 76)):
            self.runs_list.heading(column, text=heading)
            self.runs_list.column(column, width=width, minwidth=width, anchor="center", stretch=False)
        self.runs_list.grid(row=1, column=0, sticky="ns")
        scrollbar = ttk.Scrollbar(panel, orient="vertical", command=self.runs_list.yview)
        scrollbar.grid(row=1, column=1, sticky="ns")
        self.runs_list.configure(yscrollcommand=scrollbar.set)
        self.runs_list.tag_configure("late", foreground="darkorange")
        self.runs_list.bind("<ButtonRelease-1>", self._on_click)

        ttk.Label(panel, text="Click a run to tick or untick it.", foreground="gray").grid(
            row=2, column=0, columnspan=2, sticky="w", pady=(4, 0))

        buttons = ttk.Frame(panel)
        buttons.grid(row=3, column=0, columnspan=2, sticky="ew", pady=(6, 0))
        ttk.Button(buttons, text="Select all", command=lambda: self._select(self.runs_list.get_children())).pack(
            side="left")
        ttk.Button(buttons, text="Clear", command=lambda: self._select([])).pack(side="left", padx=6)

        last = ttk.Frame(panel)
        last.grid(row=4, column=0, columnspan=2, sticky="ew", pady=(6, 0))
        ttk.Label(last, text="Last").pack(side="left")
        self.last_count = tk.StringVar(value="5")
        ttk.Spinbox(last, from_=1, to=999, width=4, textvariable=self.last_count).pack(side="left", padx=4)
        ttk.Label(last, text="runs").pack(side="left")
        ttk.Button(last, text="Select", command=self._select_last).pack(side="left", padx=6)

        self.selected_label = ttk.Label(panel, text="")
        self.selected_label.grid(row=5, column=0, columnspan=2, sticky="w", pady=(8, 0))

    def _build_content(self):
        content = ttk.Frame(self)
        content.grid(row=0, column=1, sticky="nsew")
        content.columnconfigure(0, weight=1)
        content.rowconfigure(3, weight=1)

        self.included = ttk.Label(content, text="", foreground="gray", justify="left")
        self.included.grid(row=0, column=0, sticky="w")
        bold = tkfont.nametofont("TkDefaultFont").copy()
        bold.configure(size=bold.cget("size") + 2, weight="bold")
        self.verdict = ttk.Label(content, text="", font=bold, wraplength=850, justify="left")
        self.verdict.grid(row=1, column=0, sticky="w", pady=(4, 6))

        self.cards = ttk.Frame(content)
        self.cards.grid(row=2, column=0, sticky="ew")

        self.figure = Figure(figsize=(8, 4.5), dpi=100, layout="constrained")
        self.chart = ChartView(content, self.figure, zoomable=True)
        self.chart.widget.grid(row=3, column=0, sticky="nsew", pady=(8, 0))
        ttk.Label(content, text="Zoom: drag a box on a chart, or scroll the mouse wheel. Double-click a chart to go back "
                                "to the full view.", foreground="gray").grid(row=4, column=0, sticky="w")

        self.notes = ttk.Label(content, text="", justify="left", wraplength=850)
        self.notes.grid(row=5, column=0, sticky="w", pady=(6, 0))
        # Wrap the long texts at the current width of the tab
        content.bind("<Configure>", lambda event: [label.configure(wraplength=max(300, event.width - 10))
                                                   for label in (self.verdict, self.notes, self.included)])

    # ---------- Runs list ----------

    def refresh(self):
        """
        Reloads the list of saved runs. Ticked runs stay ticked if they are still in the list.
        """
        mode = MODE_FILTERS[self.mode_filter.get()]
        self.runs_list.delete(*self.runs_list.get_children())
        self.run_info = {}
        for run in self.store.list_runs():
            run_mode = run.get("setup", {}).get("emulator_mode", "original")
            if mode and run_mode != mode:
                continue
            self.run_info[run["run_id"]] = run
            late = any(result.get("timing") == "Late" for result in run["ammeters"].values())
            self.runs_list.insert("", "end", iid=run["run_id"], tags=("late",) if late else (), values=(
                CHECKED if run["run_id"] in self.checked else UNCHECKED,
                run["started_at"].replace("T", " ")[5:],  # "11-03 12:20:58"
                run_mode.capitalize(),
                run["settings"]["count"],
                f"{run['settings']['frequency_hz']:.4g}",
                " ".join(result["ammeter"]["name"][0] for result in run["ammeters"].values()),
                _late_share(run) if late else "OK",
            ))
        self.checked &= set(self.run_info)
        self._schedule_update()

    def _on_click(self, event):
        run_id = self.runs_list.identify_row(event.y)
        if not run_id or self.runs_list.identify_region(event.x, event.y) != "cell":
            return
        self.checked ^= {run_id}
        self.runs_list.set(run_id, "check", CHECKED if run_id in self.checked else UNCHECKED)
        self._schedule_update()

    def _select(self, run_ids):
        self.checked = set(run_ids)
        for run_id in self.runs_list.get_children():
            self.runs_list.set(run_id, "check", CHECKED if run_id in self.checked else UNCHECKED)
        self._schedule_update()

    def _select_last(self):
        try:
            count = max(1, int(self.last_count.get()))
        except ValueError:
            count = 5
            self.last_count.set("5")
        self._select(self.runs_list.get_children()[:count])  # The list is newest first

    # ---------- Analysis ----------

    def _schedule_update(self):
        count = len(self.checked)
        self.selected_label.configure(text=f"{count} run{'s' if count != 1 else ''} selected")
        if self.pending_update:
            self.after_cancel(self.pending_update)
        self.pending_update = self.after(UPDATE_DELAY_MS, self._update)

    def _update(self):
        self.pending_update = None
        runs, problems = [], []
        for run_id in sorted(self.checked):
            try:
                if run_id not in self.loaded:
                    self.loaded[run_id] = self.store.load(run_id)
                runs.append(self.loaded[run_id])
            except (OSError, ValueError) as error:
                problems.append(f"Skipped run {run_id}: {error}")

        if not runs:
            self._show_empty("\n".join(problems) or "Tick one or more runs in the list to compare the ammeters.")
            return
        comparisons = assess_ammeters(runs)
        self._show_included(runs, problems)
        notes = assessment_notes(comparisons)
        self.verdict.configure(text=notes[0])
        self.notes.configure(text="\n".join(f"• {note}" for note in notes[1:]))
        self._show_cards(comparisons)
        self._draw_charts(runs, comparisons)

    def _show_empty(self, message: str):
        self.included.configure(text="", foreground="gray")
        self.verdict.configure(text=message)
        self.notes.configure(text="")
        for card in self.cards.winfo_children():
            card.destroy()
        self.figure.clear()
        self.chart.draw()

    def _show_included(self, runs: list, problems: list):
        readings = sum(len(result.readings) for run in runs for result in run.results.values())
        lines = [f"Using {len(runs)} run{'s' if len(runs) > 1 else ''} "
                 f"({runs[0].started_at:%d/%m %H:%M} - {runs[-1].started_at:%d/%m %H:%M}), {readings} readings in total."]
        warning = False
        if len({run.emulator_mode for run in runs}) > 1:
            lines.append("Warning: the selected runs used different emulator modes (original and realistic), "
                         "so the results mix two different setups. Use the \"Show\" filter to pick one mode.")
            warning = True
        if len({run.settings for run in runs}) > 1:
            lines.append("Note: the selected runs used different sampling settings.")
        late = timing_note(runs)
        if late:
            lines.append(late)
            warning = True
        lines += problems
        self.included.configure(text="\n".join(lines), foreground="darkorange" if warning or problems else "gray")

    def _show_cards(self, comparisons: list):
        for card in self.cards.winfo_children():
            card.destroy()
        bold = tkfont.nametofont("TkDefaultFont").copy()
        bold.configure(weight="bold")
        for column, comparison in enumerate(comparisons):
            self.cards.columnconfigure(column, weight=1, uniform="cards")
            color = to_hex(ammeter_color(comparison.ammeter.type))
            card = tk.Frame(self.cards, highlightbackground=color, highlightcolor=color,
                            highlightthickness=3 if comparison.rank == 1 else 1, padx=8, pady=4)
            card.grid(row=0, column=column, sticky="nsew", padx=(0 if column == 0 else 8, 0))
            title = f"#{comparison.rank}  {comparison.ammeter.name}" if comparison.rank else \
                f"{comparison.ammeter.name}  (not ranked)"
            if comparison.rank == 1:
                title += "   ★ most reliable"
            tk.Label(card, text=title, font=bold, fg=color).grid(row=0, column=0, columnspan=2, sticky="w")

            cv = "-" if comparison.cv is None else f"{comparison.cv:.1f} %"
            if comparison.cv_interval:
                cv += f"  ({comparison.cv_interval[0]:.0f}-{comparison.cv_interval[1]:.0f} %)"
            rows = [
                ("Mean", _amps(comparison.mean)),
                ("Median", _amps(comparison.median)),
                ("Std dev", _amps(comparison.std_dev)),
                ("Min / Max", f"{_amps(comparison.min)} / {_amps(comparison.max)}"),
                ("CV (95% range)", cv),
                ("Success rate", f"{comparison.success_rate:.1f} %  ({comparison.readings}/{comparison.expected})"),
                ("Run-to-run CV", "-" if comparison.run_to_run_cv is None else f"{comparison.run_to_run_cv:.1f} %"),
                ("Timing", "OK" if comparison.late_runs == 0 else
                 f"Late in {comparison.late_runs} of {comparison.runs} run{'s' if comparison.runs > 1 else ''}"),
                ("Late readings", comparison.late_text() or "-"),
                ("Max delay", f"{comparison.max_delay * 1000:.0f} ms"),
            ]
            for row, (label, value) in enumerate(rows, start=1):
                tk.Label(card, text=label, fg="gray").grid(row=row, column=0, sticky="w")
                late = label in ("Timing", "Late readings", "Max delay") and comparison.late_runs
                tk.Label(card, text=value, fg="darkorange" if late else "black").grid(row=row, column=1, sticky="w",
                                                                                     padx=(10, 0))

    def _draw_charts(self, runs: list, comparisons: list):
        self.figure.clear()
        (cv_axis, spread_axis), (runs_axis, range_axis) = self.figure.subplots(2, 2)
        names = [c.ammeter.name for c in comparisons]
        colors = [ammeter_color(c.ammeter.type) for c in comparisons]
        positions = range(len(comparisons))

        # 1. Precision: CV per ammeter, with the bootstrap 95% range as error bars
        cvs = [c.cv or 0 for c in comparisons]
        bars = cv_axis.bar(positions, cvs, color=colors, alpha=0.6, edgecolor="black",
                           linewidth=[2 if c.rank == 1 else 0.5 for c in comparisons])
        for position, c in zip(positions, comparisons):
            if c.cv_interval:
                cv_axis.errorbar(position, c.cv, yerr=[[c.cv - c.cv_interval[0]], [c.cv_interval[1] - c.cv]],
                                 fmt="none", ecolor="black", capsize=5)
        cv_axis.bar_label(bars, labels=["-" if c.cv is None else f"{c.cv:.1f}%" for c in comparisons],
                          label_type="center", fontsize=8)
        cv_axis.set_xticks(list(positions), names)
        cv_axis.set_ylabel("CV (%)")
        cv_axis.set_title("1. Precision: CV per ammeter (lower is better)", fontsize=10, loc="left")
        cv_axis.margins(y=0.2)
        cv_axis.grid(True, axis="y", alpha=0.3)

        # 2. Spread of the readings, each divided by its ammeter's mean, so all ammeters share one scale
        data = [(position, [current / c.mean for current in self._currents(runs, c)])
                for position, c in zip(positions, comparisons) if c.mean]
        if data:
            boxes = spread_axis.boxplot([values for _, values in data], positions=[p for p, _ in data], widths=0.5,
                                        patch_artist=True, showmeans=True, medianprops={"color": "black"},
                                        meanprops={"markerfacecolor": "white", "markeredgecolor": "black"})
            for box, (position, _) in zip(boxes["boxes"], data):
                box.set_facecolor(colors[position])
                box.set_alpha(0.5)
        spread_axis.axhline(1, color="gray", linestyle="--", linewidth=1)
        spread_axis.set_xticks(list(positions), names)
        spread_axis.set_ylabel("Reading ÷ mean")
        spread_axis.set_title("2. Spread relative to each ammeter's mean", fontsize=10, loc="left")
        spread_axis.grid(True, axis="y", alpha=0.3)

        # 3. Consistency: each run's average as % of the ammeter's overall average
        if len(runs) > 1:
            for c, color in zip(comparisons, colors):
                points = [(index, 100 * statistics.mean(run.results[c.ammeter.type].currents) / c.mean)
                          for index, run in enumerate(runs)
                          if c.mean and c.ammeter.type in run.results and run.results[c.ammeter.type].currents]
                if points:
                    runs_axis.plot([i for i, _ in points], [v for _, v in points], "o-", color=color,
                                   label=c.ammeter.name)
            runs_axis.axhline(100, color="gray", linestyle="--", linewidth=1)
            runs_axis.set_xticks(range(len(runs)), [run.started_at.strftime("%d/%m\n%H:%M:%S") for run in runs],
                                 fontsize=7, rotation=0 if len(runs) <= 8 else 45)
            runs_axis.set_ylabel("Run average (%)")
            runs_axis.legend(fontsize=8)
        else:
            runs_axis.text(0.5, 0.5, "Select 2 or more runs\nto see the consistency between runs",
                           ha="center", va="center", color="gray", transform=runs_axis.transAxes)
            runs_axis.set_xticks([])
            runs_axis.set_yticks([])
        runs_axis.set_title("3. Consistency between runs", fontsize=10, loc="left")
        runs_axis.grid(True, alpha=0.3)

        # 4. Agreement: range, mean and median of each ammeter on a log scale, so very different currents fit
        for position, c, color in zip(positions, comparisons, colors):
            if c.mean is None:
                continue
            range_axis.vlines(position, c.min, c.max, color=color, linewidth=6, alpha=0.4,
                              label="Min - max" if position == 0 else None)
            range_axis.plot(position, c.mean, "^", color="black", label="Mean" if position == 0 else None)
            range_axis.plot(position, c.median, "_", color="black", markersize=18, markeredgewidth=2,
                            label="Median" if position == 0 else None)
        range_axis.set_yscale("log")
        range_axis.set_xticks(list(positions), names)
        range_axis.set_xlim(-0.6, len(comparisons) - 0.4)
        range_axis.set_ylabel("Current (A), log scale")
        range_axis.set_title("4. Agreement: range of the readings", fontsize=10, loc="left")
        range_axis.legend(fontsize=8, loc="best")
        range_axis.grid(True, axis="y", which="major", alpha=0.3)
        self.chart.draw()

    @staticmethod
    def _currents(runs: list, comparison) -> list:
        return [current for run in runs if comparison.ammeter.type in run.results
                for current in run.results[comparison.ammeter.type].currents]


def _late_share(run: dict) -> str:
    """
    "Late 13.7%" for a saved run (the share of late measurements), or "Late" if the run didn't count them.
    """
    results = run["ammeters"].values()
    if any(result.get("late_readings") is None for result in results):
        return "Late"
    attempted = sum(result["collected"] + len(result["errors"]) for result in results)
    late = sum(result["late_readings"] for result in results)
    return f"Late {100 * late / attempted:.1f}%" if attempted else "Late"


def _amps(value) -> str:
    return "-" if value is None else f"{value:.4g} A"
