import queue
import sys
import threading
import tkinter as tk
from tkinter import ttk

from matplotlib.figure import Figure

from src.gui.analysis_tab import AnalysisTab
from src.gui.chart_view import ChartView, ammeter_color
from src.gui.history_tab import HistoryTab
from src.testing.ammeters import AMMETERS
from src.testing.analysis import compare_ammeters, comparison_text
from src.testing.result_store import ResultStore
from src.testing.results import REPORT_COLUMNS, SamplingSettings, TestRun
from src.testing.sampling import RECOMMENDED_MAX_FREQUENCY_HZ
from src.testing.test_framework import AmmeterTestFramework

# Setting name -> (label, type of the value)
SETTINGS = {
    "count": ("Number of measurements", int),
    "duration": ("Total test duration (s)", float),
    "frequency": ("Sampling frequency (Hz)", float),
}

REFRESH_MS = 250  # How often the window takes new readings from the sampling threads and redraws the chart


class MeasurementApp:
    """
    Window with three tabs:
    "New test"            - set the sampling settings, choose the ammeters, run the measurement,
                            watch the readings live and see the results when the test ends.
    "History"             - see, compare and delete saved test runs.
    "Accuracy assessment" - compare the ammeter types over runs picked by hand.
    """

    def __init__(self, realistic: bool = False, set_realistic=None, device_constants=None):
        """
        realistic: if the emulators start in realistic mode (fixed device constants).
        set_realistic(bool): switches the emulators' mode. If not given, the mode can't be changed in the window.
        device_constants(): returns the emulators' fixed device constants, saved with every realistic test run.
        """
        self.set_realistic = set_realistic
        self.get_device_constants = device_constants
        self.root = tk.Tk()
        self.root.geometry("1200x760")
        # Drawing the chart holds Python's interpreter lock. Switching threads more often (default is every 5 ms)
        # lets the sampling threads take their measurements on time while the chart is drawn.
        sys.setswitchinterval(0.0005)
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

        self.framework = AmmeterTestFramework()
        self.realistic = tk.BooleanVar(value=realistic)
        self.store = ResultStore()
        self.values = {name: tk.StringVar() for name in SETTINGS}
        self.calculate = tk.StringVar(value="frequency")
        self.selected = {ammeter_type: tk.BooleanVar(value=True) for ammeter_type in AMMETERS}
        self.entries = {}
        self.toggles = []  # "Auto" radio buttons and ammeter check boxes, disabled during a test
        self.updating_calculated_value = False

        self.readings_queue = queue.Queue()
        self.stop_event = threading.Event()
        self.running = False
        self.live_data = {}
        self.collected = 0

        self.tabs = ttk.Notebook(self.root)
        self.tabs.pack(fill="both", expand=True)
        self.test_tab = ttk.Frame(self.tabs)
        self.tabs.add(self.test_tab, text="  New test  ")
        self.history = HistoryTab(self.tabs, self.store)
        self.tabs.add(self.history, text="  History  ")
        self.analysis = AnalysisTab(self.tabs, self.store)
        self.tabs.add(self.analysis, text="  Accuracy assessment  ")

        self._build_settings_panel()
        self._build_chart_panel()
        self._build_results_panel()

        for variable in [*self.values.values(), *self.selected.values()]:
            variable.trace_add("write", lambda *_: self._on_settings_changed())
        self.calculate.trace_add("write", lambda *_: self._on_calculate_changed())
        self._on_calculate_changed()
        self.realistic.trace_add("write", lambda *_: self._on_mode_changed())
        self._on_mode_changed()

    def run(self):
        self.root.mainloop()

    # ---------- Layout ----------

    def _build_settings_panel(self):
        panel = ttk.LabelFrame(self.test_tab, text="Sampling settings", padding=10)
        panel.grid(row=0, column=0, rowspan=2, sticky="ns", padx=10, pady=10)

        ttk.Label(panel, text="Auto").grid(row=0, column=2)
        for row, (name, (label, _)) in enumerate(SETTINGS.items(), start=1):
            ttk.Label(panel, text=label).grid(row=row, column=0, sticky="w", pady=4)
            entry = ttk.Entry(panel, textvariable=self.values[name], width=12)
            entry.grid(row=row, column=1, padx=6)
            self.entries[name] = entry
            radio = ttk.Radiobutton(panel, variable=self.calculate, value=name)
            radio.grid(row=row, column=2)
            self.toggles.append(radio)

        ttk.Label(panel, text="Enter two values. The value marked\n\"Auto\" is calculated automatically.",
                  foreground="gray").grid(row=4, column=0, columnspan=3, sticky="w", pady=(8, 0))

        ammeters_frame = ttk.LabelFrame(panel, text="Ammeters to test", padding=6)
        ammeters_frame.grid(row=5, column=0, columnspan=3, sticky="ew", pady=(12, 0))
        for ammeter_type, ammeter in AMMETERS.items():
            check = ttk.Checkbutton(ammeters_frame, text=f"{ammeter.name}  (port {ammeter.port})",
                                    variable=self.selected[ammeter_type])
            check.pack(anchor="w")
            self.toggles.append(check)

        emulators_frame = ttk.LabelFrame(panel, text="Emulators", padding=6)
        emulators_frame.grid(row=10, column=0, columnspan=3, sticky="ew", pady=(16, 0))
        realistic_check = ttk.Checkbutton(emulators_frame, text="Realistic (fixed device constants)",
                                          variable=self.realistic)
        realistic_check.pack(anchor="w")
        if self.set_realistic:
            self.toggles.append(realistic_check)
            explanation = "Resistance, calibration factor and time\nstep are chosen once and stay the same\n" \
                          "until the program closes."
        else:
            realistic_check.configure(state="disabled")
            explanation = "The emulators' mode can't be changed\nfrom this window."
        ttk.Label(emulators_frame, text=explanation, foreground="gray").pack(anchor="w")
        self.constants_label = ttk.Label(emulators_frame, text="", foreground="gray")
        self.constants_label.pack(anchor="w")

        self.message = ttk.Label(panel, text="", wraplength=260)
        self.message.grid(row=6, column=0, columnspan=3, sticky="w", pady=8)

        buttons = ttk.Frame(panel)
        buttons.grid(row=7, column=0, columnspan=3, pady=8)
        self.start_button = ttk.Button(buttons, text="Start measurement", command=self._start)
        self.start_button.pack(side="left", padx=4)
        self.stop_button = ttk.Button(buttons, text="Stop", command=self._stop, state="disabled")
        self.stop_button.pack(side="left", padx=4)

        self.progress = ttk.Progressbar(panel, length=260)
        self.progress.grid(row=8, column=0, columnspan=3, pady=(8, 2))
        self.status = ttk.Label(panel, text="Ready")
        self.status.grid(row=9, column=0, columnspan=3, sticky="w")

    def _build_chart_panel(self):
        self.figure = Figure(figsize=(9, 5.5), dpi=100, layout="constrained")
        self.axes = {}
        self.lines = {}
        first_axis = None
        for index, ammeter_type in enumerate(AMMETERS):
            axis = self.figure.add_subplot(len(AMMETERS), 1, index + 1, sharex=first_axis)
            first_axis = first_axis or axis
            axis.set_ylabel("Current (A)")
            axis.grid(True, alpha=0.3)
            self.lines[ammeter_type], = axis.plot([], [], ".-", color=ammeter_color(ammeter_type))
            self.axes[ammeter_type] = axis
        self.axes[list(AMMETERS)[-1]].set_xlabel("Time (s)")
        self._set_chart_titles()

        self.chart = ChartView(self.test_tab, self.figure)
        self.chart.widget.grid(row=0, column=1, sticky="nsew", padx=(0, 10), pady=(10, 0))
        self.test_tab.columnconfigure(1, weight=1)
        self.test_tab.rowconfigure(0, weight=1)

    def _set_chart_titles(self, tested_types=None):
        for ammeter_type, axis in self.axes.items():
            ammeter = AMMETERS[ammeter_type]
            title = f"{ammeter.name}  -  {ammeter.method}"
            if tested_types is not None and ammeter_type not in tested_types:
                title += "   (not tested)"
            axis.set_title(title, fontsize=10, loc="left")

    def _build_results_panel(self):
        panel = ttk.LabelFrame(self.test_tab, text="Results", padding=10)
        panel.grid(row=1, column=1, sticky="ew", padx=(0, 10), pady=10)

        self.results_summary = ttk.Label(panel, text="Results will appear here when the test ends.")
        self.results_summary.pack(anchor="w")

        self.results_table = ttk.Treeview(panel, columns=REPORT_COLUMNS, show="headings", height=len(AMMETERS))
        for column in REPORT_COLUMNS:
            self.results_table.heading(column, text=column)
            self.results_table.column(column, width=60, minwidth={"Max delay (ms)": 95, "Timing": 135}.get(column, 60),
                                      anchor="center", stretch=True)
        self.results_table.pack(fill="x", pady=6)

        self.results_errors = ttk.Label(panel, text="", foreground="red", justify="left")
        self.results_errors.pack(anchor="w")

    # ---------- Settings ----------

    def _read_value(self, name: str):
        """
        Returns the value the user entered for a setting, or None if it is empty.
        Raises ValueError if it is not a positive number.
        """
        label, number_type = SETTINGS[name]
        text = self.values[name].get().strip()
        if text == "":
            return None
        try:
            value = number_type(text)
        except ValueError:
            kind = "a whole number" if number_type is int else "a number"
            raise ValueError(f"{label} must be {kind}.")
        if value <= 0:
            raise ValueError(f"{label} must be greater than 0.")
        return value

    def _get_settings(self) -> SamplingSettings:
        """
        Returns the settings from the entered values, or raises ValueError with a message.
        The value marked "Auto" is ignored and calculated.
        """
        given = {name: self._read_value(name) for name in SETTINGS if name != self.calculate.get()}
        missing = [SETTINGS[name][0].lower() for name, value in given.items() if value is None]
        if missing:
            raise ValueError(f"Enter the {' and the '.join(missing)}.")
        return SamplingSettings.from_values(**given)

    def _selected_types(self) -> list:
        return [ammeter_type for ammeter_type, selected in self.selected.items() if selected.get()]

    def _on_calculate_changed(self):
        for name, entry in self.entries.items():
            entry.configure(state="readonly" if name == self.calculate.get() else "normal")
        self._on_settings_changed()

    def _on_settings_changed(self):
        """
        Recalculates the "Auto" value and shows if the settings can be used.
        """
        if self.updating_calculated_value or self.running:
            return
        calculate = self.calculate.get()
        try:
            settings = self._get_settings()
            if not self._selected_types():
                raise ValueError("Select at least one ammeter to test.")
        except ValueError as error:
            if "ammeter" not in str(error):
                self._set_calculated_value("")
            self._show_message(str(error), "red")
            self.start_button.configure(state="disabled")
            return

        value = getattr(settings, calculate)
        self._set_calculated_value(str(value) if calculate == "count" else f"{value:.6g}")
        if settings.frequency > RECOMMENDED_MAX_FREQUENCY_HZ:
            self._show_message(f"Warning: above {RECOMMENDED_MAX_FREQUENCY_HZ} Hz the ammeters may not answer "
                               f"fast enough and some measurements may be late.", "darkorange")
        else:
            self._show_message(f"One measurement every {settings.interval:.6g} s per ammeter.", "green")
        self.start_button.configure(state="normal")

    def _on_mode_changed(self):
        """
        Switches the emulators between original and realistic mode.
        """
        realistic = self.realistic.get()
        mode = "realistic" if realistic else "original"
        if self.set_realistic:
            self.set_realistic(realistic)
        self.framework.setup["emulator_mode"] = mode
        self.root.title(f"Ammeter Measurement  -  {mode} emulators")
        self._show_device_constants()

    def _device_constants(self) -> dict:
        return self.get_device_constants() if self.get_device_constants else {}

    def _show_device_constants(self):
        if not self.realistic.get():
            self.constants_label.configure(text="")
            return
        constants = self._device_constants()
        lines = [f"{AMMETERS[ammeter_type].name}: {name} = {value:.6g}"
                 for ammeter_type, values in constants.items() if ammeter_type in AMMETERS
                 for name, value in values.items()]
        self.constants_label.configure(text="\n".join(lines) if lines else
                                       "The constants are chosen at the first\nmeasurement.")

    def _set_calculated_value(self, text: str):
        self.updating_calculated_value = True
        self.values[self.calculate.get()].set(text)
        self.updating_calculated_value = False

    def _show_message(self, text: str, color: str):
        self.message.configure(text=text, foreground=color)

    # ---------- Measurement ----------

    def _start(self):
        try:
            settings = self._get_settings()
        except ValueError as error:
            self._show_message(str(error), "red")
            return
        ammeter_types = self._selected_types()
        self._set_running(True)

        # Clear the previous test
        self.live_data = {ammeter_type: ([], []) for ammeter_type in AMMETERS}
        for ammeter_type, axis in self.axes.items():
            self.lines[ammeter_type].set_data([], [])
            axis.set_xlim(0, settings.duration)
        self._set_chart_titles(ammeter_types)
        self.chart.draw()
        self.results_table.delete(*self.results_table.get_children())
        self.results_summary.configure(text="Measuring...")
        self.results_errors.configure(text="")
        self.collected = 0
        self.progress.configure(maximum=settings.count * len(ammeter_types), value=0)
        self.status.configure(text="Measuring...")

        self.stop_event = threading.Event()
        threading.Thread(target=self._measure, args=(ammeter_types, settings, self.stop_event), daemon=True).start()
        self.root.after(REFRESH_MS, self._refresh)

    def _measure(self, ammeter_types: list, settings: SamplingSettings, stop_event: threading.Event):
        """
        Runs in a background thread so the window stays responsive. Sends everything to the window through the queue.
        """
        def on_reading(ammeter_type, seconds, current):
            self.readings_queue.put(("reading", ammeter_type, seconds, current))

        try:
            run = self.framework.run_tests(ammeter_types, settings, stop_event, on_reading)
        except Exception as error:
            self.readings_queue.put(("failed", str(error)))
            return
        self.readings_queue.put(("done", run))

    def _stop(self):
        self.stop_event.set()
        self.stop_button.configure(state="disabled")
        self.status.configure(text="Stopping...")

    def _refresh(self):
        """
        Takes the new readings from the queue and updates the chart. Repeats until the test ends.
        """
        finished = None
        collected_before = self.collected
        while True:
            try:
                message = self.readings_queue.get_nowait()
            except queue.Empty:
                break
            if message[0] == "reading":
                _, ammeter_type, seconds, current = message
                times, currents = self.live_data[ammeter_type]
                times.append(seconds)
                currents.append(current)
                self.collected += 1
            else:
                finished = message

        if self.collected > collected_before:
            for ammeter_type, (times, currents) in self.live_data.items():
                self.lines[ammeter_type].set_data(times, currents)
                self.axes[ammeter_type].relim()
                self.axes[ammeter_type].autoscale_view(scalex=False)
            self.chart.draw()
        self.progress.configure(value=self.collected)
        self.status.configure(text=f"Collected {self.collected} of {int(self.progress['maximum'])} measurements")

        if finished is None:
            self.root.after(REFRESH_MS, self._refresh)
        elif finished[0] == "done":
            self._show_results(finished[1])
        else:
            self.results_summary.configure(text=f"The test failed: {finished[1]}")
            self._set_running(False)

    def _show_results(self, run: TestRun):
        if run.emulator_mode == "realistic":
            run.setup["device_constants"] = {ammeter_type: values for ammeter_type, values
                                             in self._device_constants().items() if ammeter_type in run.results}
            self._show_device_constants()
        try:
            folder = self.store.save(run, self.chart.png())
            saved = f"Saved as run {run.run_id} (see the History tab)"
            print(f"\nResults saved to: {folder}")
            self.history.refresh()
            self.analysis.refresh()
        except OSError as error:
            saved = f"Could not save the results: {error}"
        best = compare_ammeters([run])[0]
        verdict = f"Most reliable in this run: {best.ammeter.name} (CV {best.cv:.1f}%). " \
                  f"Compare more runs in the Accuracy assessment tab." if best.rank and len(run.results) > 1 else ""
        self.results_summary.configure(text="\n".join(line for line in (run.summary(), saved, verdict) if line))
        for row in run.report_rows():
            self.results_table.insert("", "end", values=[row[column] for column in REPORT_COLUMNS])

        errors = run.errors()
        if errors:
            shown = errors[:5]
            if len(errors) > len(shown):
                shown.append(f"... and {len(errors) - len(shown)} more errors")
            self.results_errors.configure(text="\n".join(shown))
        self.status.configure(text="Stopped" if run.stopped else "Finished")
        # The same report, as text in the terminal
        print("\n" + run.to_text() + "\n\n" + comparison_text([run]) + "\n")
        self._set_running(False)

    def _set_running(self, running: bool):
        self.running = running
        for name, entry in self.entries.items():
            entry.configure(state="readonly" if name == self.calculate.get() or running else "normal")
        for toggle in self.toggles:
            toggle.configure(state="disabled" if running else "normal")
        self.stop_button.configure(state="normal" if running else "disabled")
        if running:
            self.start_button.configure(state="disabled")
        else:
            self._on_settings_changed()

    def _on_close(self):
        self.stop_event.set()
        self.root.destroy()
