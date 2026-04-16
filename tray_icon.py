import threading
from typing import Callable


try:
    import pystray
    from PIL import Image, ImageDraw
except ImportError:
    pystray = None
    Image = None
    ImageDraw = None


class SystemTrayIcon(object):
    def __init__(self, on_quit: Callable[[], None], on_settings: Callable[[], None]):
        self._on_quit = on_quit
        self._on_settings = on_settings
        self._thread = None
        self._icon = None

    def start(self):
        if pystray is None or Image is None or ImageDraw is None:
            print("Warning: pystray/Pillow not installed; system tray is disabled.")
            return

        self._thread = threading.Thread(target=self._run, daemon=True, name="fluxvoice-tray")
        self._thread.start()

    def stop(self):
        if self._icon is not None:
            try:
                self._icon.stop()
            except Exception:
                pass

        if self._thread is not None and self._thread.is_alive():
            self._thread.join(timeout=1.5)

    def _run(self):
        image = self._build_icon_image()
        menu = pystray.Menu(
            pystray.MenuItem("Settings", self._handle_settings),
            pystray.MenuItem("Quit", self._handle_quit),
        )
        self._icon = pystray.Icon("fluxvoice", image, "FluxVoice", menu)
        self._icon.run()

    def _handle_settings(self, icon, item):
        self._on_settings()

    def _handle_quit(self, icon, item):
        self._on_quit()

    def _build_icon_image(self):
        size = 64
        image = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        draw = ImageDraw.Draw(image)
        draw.ellipse((14, 14, 50, 50), fill=(46, 204, 113, 255))
        draw.ellipse((24, 24, 40, 40), fill=(255, 255, 255, 255))
        return image

