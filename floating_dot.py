import threading
import tkinter as tk

from ui_state import UIState, UIStateBus


class FloatingDotWindow(object):
    def __init__(self, state_bus: UIStateBus, shutdown_event: threading.Event):
        self._state_bus = state_bus
        self._shutdown_event = shutdown_event
        self._window_size = 48
        self._bottom_padding = 36
        self._transparent_key = "#010203"

        self._root = tk.Tk()
        self._root.overrideredirect(True)
        self._root.attributes("-topmost", True)
        self._root.configure(bg=self._transparent_key)
        try:
            self._root.attributes("-transparentcolor", self._transparent_key)
        except tk.TclError:
            pass

        self._canvas = tk.Canvas(
            self._root,
            width=self._window_size,
            height=self._window_size,
            bg=self._transparent_key,
            highlightthickness=0,
            bd=0,
        )
        self._canvas.pack()

        self._dot_id = None
        self._current_state = None
        self._place_bottom_center()

    def _place_bottom_center(self):
        screen_width = self._root.winfo_screenwidth()
        screen_height = self._root.winfo_screenheight()
        x = int((screen_width - self._window_size) / 2)
        y = int(screen_height - self._window_size - self._bottom_padding)
        self._root.geometry("{0}x{0}+{1}+{2}".format(self._window_size, x, y))

    def _render_state(self, state: UIState):
        if state == self._current_state:
            return

        self._current_state = state

        if state == UIState.PROCESSING:
            radius = 7
            color = "#f39c12"
        elif state == UIState.PLAYING:
            radius = 8
            color = "#2ecc71"
        else:
            radius = 1
            color = "#7f8c8d"

        center = int(self._window_size / 2)
        x0 = center - radius
        y0 = center - radius
        x1 = center + radius
        y1 = center + radius

        if self._dot_id is None:
            self._dot_id = self._canvas.create_oval(x0, y0, x1, y1, fill=color, outline="")
        else:
            self._canvas.coords(self._dot_id, x0, y0, x1, y1)
            self._canvas.itemconfig(self._dot_id, fill=color)

    def _tick(self):
        latest_state = self._state_bus.drain_latest()
        if latest_state is not None:
            self._render_state(latest_state)

        if self._shutdown_event.is_set():
            try:
                self._root.quit()
            except tk.TclError:
                pass
            return

        try:
            self._root.after(40, self._tick)
        except tk.TclError:
            return

    def run(self):
        self._render_state(UIState.IDLE)
        self._tick()
        try:
            self._root.mainloop()
        except KeyboardInterrupt:
            self._shutdown_event.set()
        finally:
            try:
                self._root.destroy()
            except tk.TclError:
                pass


