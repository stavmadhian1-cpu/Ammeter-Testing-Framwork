"""
Compares the ammeter types with each other, over one or more test runs.

True accuracy can't be measured here: that needs a known reference current, and the emulators return random values.
So the ammeters are compared by what can be measured:
- reliability: how many of the requested measurements arrived (success rate) and if they were on time,
- precision: how much the readings spread (coefficient of variation, 95% confidence interval of the mean),
- consistency: how much the average changes from run to run,
- agreement: if the ammeters' averages agree with each other.
"""
import math
import random
import statistics
from dataclasses import dataclass

from src.testing.ammeters import Ammeter
from src.testing.sampling import RECOMMENDED_MAX_FREQUENCY_HZ

COMPARISON_COLUMNS = ("Rank", "Ammeter", "Runs", "Success rate", "Mean (A)", "Std dev (A)", "CV (%)",
                      "95% CI of mean", "Run-to-run CV (%)", "Timing")

# Two-sided 95% critical values of Student's t distribution, by degrees of freedom (n - 1).
# Above 30 the normal distribution value 1.96 is close enough.
T_CRITICAL_95 = {1: 12.706, 2: 4.303, 3: 3.182, 4: 2.776, 5: 2.571, 6: 2.447, 7: 2.365, 8: 2.306, 9: 2.262,
                 10: 2.228, 11: 2.201, 12: 2.179, 13: 2.160, 14: 2.145, 15: 2.131, 16: 2.120, 17: 2.110,
                 18: 2.101, 19: 2.093, 20: 2.086, 21: 2.080, 22: 2.074, 23: 2.069, 24: 2.064, 25: 2.060,
                 26: 2.056, 27: 2.052, 28: 2.048, 29: 2.045, 30: 2.042}

MIN_READINGS_FOR_RANKING = 10  # With fewer readings the statistics are not reliable enough to rank
CLOSE_CV_RATIO = 0.2           # CVs closer than 20% of each other are too close to tell the ammeters apart


@dataclass
class AmmeterComparison:
    """
    The comparison values of one ammeter type, over all the runs it was tested in.
    Values that can't be calculated are None.
    """
    ammeter: Ammeter
    runs: int
    readings: int
    expected: int
    late_runs: int
    mean: float = None
    std_dev: float = None
    cv: float = None             # Std dev / mean, in %
    ci95: float = None           # Half width of the 95% confidence interval of the mean, in % of the mean
    run_to_run_cv: float = None  # CV of the run averages, in % (needs at least 2 runs)
    rank: int = None
    median: float = None
    min: float = None
    max: float = None
    cv_interval: tuple = None    # Bootstrap 95% range of the CV, in % (only filled by `assess_ammeters`)
    max_delay: float = 0.0       # Largest delay from the planned measurement time over all runs, in seconds
    late_readings: int = None    # Late measurements over all runs (None if a run didn't count them)
    attempted: int = 0           # Measurements taken over all runs, successful or not

    def late_text(self) -> str:
        """
        How many measurements were late, e.g. "82 of 1800 (4.6%)", or "" if not known.
        """
        if self.late_readings is None or not self.attempted:
            return ""
        return f"{self.late_readings:,} of {self.attempted:,} ({100 * self.late_readings / self.attempted:.1f}%)"

    @property
    def success_rate(self) -> float:
        return 100 * self.readings / self.expected if self.expected else 0.0

    def report_row(self) -> dict:
        """
        Returns this comparison as text values for each of the COMPARISON_COLUMNS.
        """
        return {
            "Rank": str(self.rank) if self.rank else "-",
            "Ammeter": self.ammeter.name,
            "Runs": str(self.runs),
            "Success rate": f"{self.success_rate:.1f}% ({self.readings}/{self.expected})",
            "Mean (A)": _format(self.mean, ".6g"),
            "Std dev (A)": _format(self.std_dev, ".6g"),
            "CV (%)": _format(self.cv, ".1f"),
            "95% CI of mean": "-" if self.ci95 is None else f"±{self.ci95:.1f}%",
            "Run-to-run CV (%)": _format(self.run_to_run_cv, ".1f"),
            "Timing": "OK" if self.late_runs == 0 else f"Late in {self.late_runs} of {self.runs} runs"
                      + (f" ({100 * self.late_readings / self.attempted:.1f}% of readings)" if self.late_text() else ""),
        }


def compare_ammeters(runs: list) -> list:
    """
    Compares the ammeter types over the given test runs. Returns one AmmeterComparison per ammeter type,
    best first. The ranking is: highest success rate first, then lowest CV (the steadier readings).
    Ammeters with too few readings are not ranked and come last.
    """
    comparisons = []
    ammeter_types = list(dict.fromkeys(ammeter_type for run in runs for ammeter_type in run.results))
    for ammeter_type in ammeter_types:
        results = [run.results[ammeter_type] for run in runs if ammeter_type in run.results]
        currents = [current for result in results for current in result.currents]
        comparison = AmmeterComparison(
            ammeter=results[0].ammeter,
            runs=len(results),
            readings=len(currents),
            expected=sum(result.settings.count for result in results),
            late_runs=sum(not result.timing_ok for result in results),
            max_delay=max(result.max_delay for result in results),
            late_readings=None if any(result.late_count is None for result in results)
            else sum(result.late_count for result in results),
            attempted=sum(result.attempted for result in results),
        )
        if currents:
            comparison.mean = statistics.mean(currents)
            comparison.median = statistics.median(currents)
            comparison.min = min(currents)
            comparison.max = max(currents)
        if len(currents) > 1:
            comparison.std_dev = statistics.stdev(currents)
            if comparison.mean:
                comparison.cv = 100 * comparison.std_dev / abs(comparison.mean)
                t = T_CRITICAL_95.get(len(currents) - 1, 1.96)
                comparison.ci95 = 100 * t * comparison.std_dev / math.sqrt(len(currents)) / abs(comparison.mean)
        run_means = [statistics.mean(result.currents) for result in results if result.currents]
        if len(run_means) > 1 and statistics.mean(run_means):
            comparison.run_to_run_cv = 100 * statistics.stdev(run_means) / abs(statistics.mean(run_means))
        comparisons.append(comparison)

    rankable = [c for c in comparisons if c.readings >= MIN_READINGS_FOR_RANKING and c.cv is not None]
    rankable.sort(key=lambda c: (-c.success_rate, c.cv))
    for rank, comparison in enumerate(rankable, start=1):
        comparison.rank = rank
    return rankable + [c for c in comparisons if c not in rankable]


def comparison_notes(comparisons: list) -> list:
    """
    Returns the conclusions of the comparison as short sentences for the user.
    """
    notes = []
    ranked = [c for c in comparisons if c.rank]
    if len(ranked) > 1:
        best = ranked[0]
        steadiest = min(ranked, key=lambda c: c.cv)
        if steadiest is best:
            notes.append(f"Most reliable: {best.ammeter.name} ({best.ammeter.method}) - success rate "
                         f"{best.success_rate:.1f}% and the steadiest readings (CV {best.cv:.1f}%).")
        else:
            notes.append(f"Most reliable: {best.ammeter.name} ({best.ammeter.method}) - the highest success rate "
                         f"({best.success_rate:.1f}%). {steadiest.ammeter.name} has steadier readings "
                         f"(CV {steadiest.cv:.1f}% vs {best.cv:.1f}%) but lost more measurements "
                         f"({steadiest.success_rate:.1f}% success rate).")
        second = ranked[1]
        if second.success_rate == best.success_rate and second.cv - best.cv < CLOSE_CV_RATIO * best.cv:
            notes.append(f"Too close to call: {best.ammeter.name} and {second.ammeter.name} have almost the same CV "
                         f"({best.cv:.1f}% vs {second.cv:.1f}%), so their order may change from run to run. "
                         f"Run longer tests (more measurements) to tell them apart.")
    elif len(ranked) == 1:
        notes.append(f"Only {ranked[0].ammeter.name} has enough readings to be ranked.")
    not_ranked = [c.ammeter.name for c in comparisons if not c.rank]
    if not_ranked:
        notes.append(f"Not ranked (fewer than {MIN_READINGS_FOR_RANKING} readings): {', '.join(not_ranked)}.")

    means = [abs(c.mean) for c in comparisons if c.mean]
    if len(means) > 1 and min(means) > 0:
        factor = max(means) / min(means)
        if factor > 2:
            notes.append(f"Agreement: the average currents differ by a factor of {factor:,.0f}. Ammeters measuring the "
                         f"same circuit should agree, so they don't measure the same current here: each emulator "
                         f"returns independent random values.")
        else:
            notes.append(f"Agreement: the average currents are within a factor of {factor:.2f} of each other.")
    notes.append("Accuracy (closeness to the real current) can't be determined without a known reference current, "
                 "so the ranking is based on reliability and precision.")
    return notes


def comparison_text(runs: list) -> str:
    """
    Returns the comparison as a text table with its conclusions.
    """
    rows = [comparison.report_row() for comparison in compare_ammeters(runs)]
    widths = {column: max([len(column)] + [len(row[column]) for row in rows]) for column in COMPARISON_COLUMNS}
    lines = [
        f"Ammeter comparison ({len(runs)} run{'s' if len(runs) > 1 else ''})",
        "  ".join(column.ljust(widths[column]) for column in COMPARISON_COLUMNS),
        "  ".join("-" * widths[column] for column in COMPARISON_COLUMNS),
    ]
    lines += ["  ".join(row[column].ljust(widths[column]) for column in COMPARISON_COLUMNS) for row in rows]
    lines += [""] + comparison_notes(compare_ammeters(runs))
    return "\n".join(lines)


BOOTSTRAP_RESAMPLES = 1000


def bootstrap_cv_interval(currents: list, resamples: int = BOOTSTRAP_RESAMPLES, seed: int = 0) -> tuple:
    """
    Returns the 95% range (low, high) of the CV in %, found with the bootstrap method:
    the readings are re-sampled (with replacement) `resamples` times, the CV is calculated for each sample,
    and the middle 95% of these CVs is the range. Returns None if there are too few readings.
    A fixed seed gives the same result for the same readings.
    """
    if len(currents) < MIN_READINGS_FOR_RANKING:
        return None
    rng = random.Random(seed)
    cvs = sorted(cv for cv in (_fast_cv(rng.choices(currents, k=len(currents))) for _ in range(resamples))
                 if cv is not None)
    if len(cvs) < resamples * 0.9:
        return None
    return cvs[int(0.025 * len(cvs))], cvs[int(0.975 * len(cvs)) - 1]


def _fast_cv(values: list):
    # statistics.stdev is exact but slow, too slow to repeat 1000 times
    mean = math.fsum(values) / len(values)
    if mean == 0:
        return None
    variance = math.fsum((value - mean) ** 2 for value in values) / (len(values) - 1)
    return 100 * math.sqrt(variance) / abs(mean)


def assess_ammeters(runs: list) -> list:
    """
    Like `compare_ammeters`, and also calculates the bootstrap 95% range of each ammeter's CV.
    """
    comparisons = compare_ammeters(runs)
    for comparison in comparisons:
        currents = [current for run in runs if comparison.ammeter.type in run.results
                    for current in run.results[comparison.ammeter.type].currents]
        comparison.cv_interval = bootstrap_cv_interval(currents)
    return comparisons


def assessment_notes(comparisons: list) -> list:
    """
    Returns the conclusions of the accuracy assessment. The first note is the verdict.
    Uses the bootstrap ranges of the CV (from `assess_ammeters`) to tell if the winner is significantly steadier.
    """
    notes = []
    ranked = [c for c in comparisons if c.rank]
    if len(ranked) > 1:
        best, second = ranked[0], ranked[1]
        name = f"{best.ammeter.name} ({best.ammeter.method})"
        if best.success_rate > second.success_rate:
            notes.append(f"Most reliable: {name} - the highest success rate ({best.success_rate:.1f}%).")
            steadiest = min(ranked, key=lambda c: c.cv)
            if steadiest is not best:
                notes.append(f"{steadiest.ammeter.name} has steadier readings (CV {steadiest.cv:.1f}% vs "
                             f"{best.cv:.1f}%), but lost more measurements ({steadiest.success_rate:.1f}% success rate).")
        else:
            notes.append(f"Most reliable: {name} - the steadiest readings (CV {best.cv:.1f}%) "
                         f"with a {best.success_rate:.1f}% success rate.")
            if best.cv_interval and second.cv_interval:
                ranges = (f"{best.ammeter.name} {best.cv_interval[0]:.1f}-{best.cv_interval[1]:.1f}%, "
                          f"{second.ammeter.name} {second.cv_interval[0]:.1f}-{second.cv_interval[1]:.1f}%")
                if best.cv_interval[1] < second.cv_interval[0]:
                    notes.append(f"Significant: {best.ammeter.name} is steadier than {second.ammeter.name} - the 95% "
                                 f"ranges of their CV don't overlap ({ranges}).")
                else:
                    notes.append(f"Not significant: the 95% ranges of the CV overlap ({ranges}), so the order of "
                                 f"{best.ammeter.name} and {second.ammeter.name} may be chance. "
                                 f"Select more runs or run longer tests.")
    elif len(ranked) == 1:
        notes.append(f"Only {ranked[0].ammeter.name} has enough readings to be ranked.")
    else:
        notes.append(f"No ammeter has enough readings to be ranked (at least {MIN_READINGS_FOR_RANKING} are needed).")
    not_ranked = [c.ammeter.name for c in comparisons if not c.rank]
    if not_ranked and ranked:
        notes.append(f"Not ranked (fewer than {MIN_READINGS_FOR_RANKING} readings): {', '.join(not_ranked)}.")

    means = [abs(c.mean) for c in comparisons if c.mean]
    if len(means) > 1 and min(means) > 0:
        factor = max(means) / min(means)
        if factor > 2:
            notes.append(f"Relative agreement: the average currents differ by a factor of {factor:,.0f}. Ammeters on "
                         f"the same circuit should agree, so here they don't measure the same current "
                         f"(each emulator returns independent random values).")
        else:
            notes.append(f"Relative agreement: the average currents are within a factor of {factor:.2f} "
                         f"of each other.")
    notes.append("Accuracy (closeness to the real current) can't be determined without a known reference: "
                 "it needs a calibrated current source or a calibrated reference meter on the same circuit. "
                 "So the ranking is based on reliability and precision.")
    return notes


def timing_note(runs: list):
    """
    Returns a note about the runs with late measurements (a delay longer than the sampling interval),
    or None if all runs kept their timing.
    """
    late = [run for run in runs if any(not result.timing_ok for result in run.results.values())]
    if not late:
        return None
    worst = max(late, key=_run_max_delay)
    results = [result for run in runs for result in run.results.values()]
    counted = ""
    if all(result.late_count is not None for result in results) and sum(r.attempted for r in results):
        late_readings, attempted = sum(r.late_count for r in results), sum(r.attempted for r in results)
        counted = f": {late_readings:,} of {attempted:,} readings ({100 * late_readings / attempted:.1f}%)"
    note = (f"Timing: {len(late)} of {len(runs)} selected run{'s' if len(runs) > 1 else ''} had late measurements"
            f"{counted}. The largest delay was {_run_max_delay(worst) * 1000:.0f} ms, in the run of "
            f"{worst.started_at:%d/%m %H:%M:%S} at {worst.settings.frequency:.4g} Hz. Late readings were taken after their planned time, so these runs "
            f"didn't keep the sampling frequency. Their readings are still included.")
    if all(run.settings.frequency > RECOMMENDED_MAX_FREQUENCY_HZ for run in late):
        note += f" Use {RECOMMENDED_MAX_FREQUENCY_HZ} Hz or less for precise timing."
    return note


def _run_max_delay(run) -> float:
    return max(result.max_delay for result in run.results.values())


def _format(value, number_format: str) -> str:
    return "-" if value is None else format(value, number_format)
