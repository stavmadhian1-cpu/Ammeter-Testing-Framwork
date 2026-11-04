import io
import tkinter as tk

# The chart is drawn with the Agg engine and shown as an image, instead of matplotlib's Tk backend,
# because the Tk backend needs a compiled DLL (_tkagg) that Windows Application Control may block.
from matplotlib.backends.backend_agg import FigureCanvasAgg
from matplotlib.figure import Figure

from src.testing.ammeters import AMMETERS


ZOOM_STEP = 0.8       # One mouse wheel step shows 80% of the current range
MIN_BOX_PIXELS = 5    # A smaller drag is treated as a click, not a zoom box


class ChartView:
    """
    Shows a matplotlib figure in the window. The figure is redrawn to fill its area when the area changes size.
    Place `widget` in the window with grid or pack.

    With zoomable=True the user can zoom into each chart of the figure:
    drag a box to zoom into it, scroll the mouse wheel to zoom in or out, double-click to go back to the full view.
    """

    def __init__(self, parent, figure: Figure, zoomable: bool = False):
        self.figure = figure
        self.canvas = FigureCanvasAgg(figure)
        self.image = None  # Keeps a reference, or Tk would discard the image
        if zoomable:
            # A Canvas, so the zoom box can be drawn over the chart image
            self.widget = tk.Canvas(parent, background="white", borderwidth=0, highlightthickness=0, cursor="crosshair")
            self.full_view = {}     # Axes -> its limits before zooming, to go back with a double-click
            self.drag_start = None  # (axes, x, y) where the zoom box started
            self.pending_draw = None
            self.widget.bind("<ButtonPress-1>", self._on_press)
            self.widget.bind("<B1-Motion>", self._on_drag)
            self.widget.bind("<ButtonRelease-1>", self._on_release)
            self.widget.bind("<Double-Button-1>", self._on_double_click)
            self.widget.bind("<MouseWheel>", lambda event: self._on_wheel(event, event.delta > 0))  # Windows, macOS
            self.widget.bind("<Button-4>", lambda event: self._on_wheel(event, True))               # Linux
            self.widget.bind("<Button-5>", lambda event: self._on_wheel(event, False))
        else:
            self.widget = tk.Label(parent, background="white", borderwidth=0, padx=0, pady=0)
        self.widget.bind("<Configure>", lambda _: self.draw())

    def draw(self):
        """
        Draws the figure at the current size of its area and shows it.
        """
        width, height = self.widget.winfo_width(), self.widget.winfo_height()
        if width < 50 or height < 50:
            return
        self.figure.set_size_inches(width / self.figure.dpi, height / self.figure.dpi)
        self.image = tk.PhotoImage(data=self.png())
        if isinstance(self.widget, tk.Canvas):
            self.widget.delete("all")
            self.widget.create_image(0, 0, anchor="nw", image=self.image)
        else:
            self.widget.configure(image=self.image)

    def png(self) -> bytes:
        png = io.BytesIO()
        self.canvas.print_png(png)
        return png.getvalue()

    # ---------- Zoom ----------

    def _axes_at(self, x: float, y: float):
        """
        Returns the chart (axes) under the window point x, y, and the point in matplotlib's display coordinates
        (pixels from the bottom left, the same size as the image).
        """
        point = (x, self.widget.winfo_height() - y)
        for axes in self.figure.axes:
            if axes.bbox.contains(*point):
                return axes, point
        return None, point

    def _set_limits(self, axes, corner_1: tuple, corner_2: tuple):
        """
        Shows the area between two display points of the chart.
        """
        # Forget charts that were cleared from the figure
        self.full_view = {old: view for old, view in self.full_view.items() if old in self.figure.axes}
        if axes not in self.full_view:
            self.full_view[axes] = (axes.get_xlim(), axes.get_ylim())
        to_data = axes.transData.inverted()
        (x1, y1), (x2, y2) = to_data.transform(corner_1), to_data.transform(corner_2)
        axes.set_xlim(min(x1, x2), max(x1, x2))
        axes.set_ylim(min(y1, y2), max(y1, y2))

    def _on_press(self, event):
        axes, _ = self._axes_at(event.x, event.y)
        self.drag_start = (axes, event.x, event.y) if axes else None

    def _on_drag(self, event):
        if self.drag_start:
            _, x, y = self.drag_start
            self.widget.delete("zoom_box")
            self.widget.create_rectangle(x, y, event.x, event.y, outline="black", dash=(4, 2), tags="zoom_box")

    def _on_release(self, event):
        self.widget.delete("zoom_box")
        if not self.drag_start:
            return
        axes, x, y = self.drag_start
        self.drag_start = None
        if abs(event.x - x) < MIN_BOX_PIXELS or abs(event.y - y) < MIN_BOX_PIXELS:
            return
        # Keep the box inside the chart it started in
        box = axes.bbox
        height = self.widget.winfo_height()
        corners = [(min(max(px, box.x0), box.x1), min(max(height - py, box.y0), box.y1))
                   for px, py in ((x, y), (event.x, event.y))]
        self._set_limits(axes, *corners)
        self.draw()

    def _on_double_click(self, event):
        axes, _ = self._axes_at(event.x, event.y)
        if axes in self.full_view:
            xlim, ylim = self.full_view.pop(axes)
            axes.set_xlim(xlim)
            axes.set_ylim(ylim)
            self.draw()

    def _on_wheel(self, event, zoom_in: bool):
        axes, (px, py) = self._axes_at(event.x, event.y)
        if not axes:
            return
        # Zoom around the mouse pointer: the point under it stays in place.
        # Working in display coordinates makes this work for log scales too.
        scale = ZOOM_STEP if zoom_in else 1 / ZOOM_STEP
        box = axes.bbox
        self._set_limits(axes, (px + (box.x0 - px) * scale, py + (box.y0 - py) * scale),
                         (px + (box.x1 - px) * scale, py + (box.y1 - py) * scale))
        # Several wheel steps in a row are drawn once
        if self.pending_draw:
            self.widget.after_cancel(self.pending_draw)
        self.pending_draw = self.widget.after(60, self._draw_pending)

    def _draw_pending(self):
        self.pending_draw = None
        self.draw()


def ammeter_color(ammeter_type: str) -> str:
    """
    Returns the chart color of an ammeter type, so each ammeter has the same color in every chart.
    """
    types = list(AMMETERS)
    return f"C{types.index(ammeter_type)}" if ammeter_type in types else "C7"
