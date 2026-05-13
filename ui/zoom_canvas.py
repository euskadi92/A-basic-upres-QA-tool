import tkinter as tk
from PIL import Image, ImageTk


class ZoomPanCanvas(tk.Canvas):
    def __init__(self, master, bg="#1f1f1f", **kwargs):
        super().__init__(master, bg=bg, highlightthickness=0, **kwargs)

        self.image = None
        self.tk_image = None

        self.zoom = 1.0
        self.pan_x = 0
        self.pan_y = 0

        self.last_x = None
        self.last_y = None

        self.bind("<Configure>", self.redraw)
        self.bind("<ButtonPress-1>", self.start_pan)
        self.bind("<B1-Motion>", self.pan)
        self.bind("<Double-Button-1>", self.reset_view)

        self.bind("<MouseWheel>", self.zoom_mouse)

    def set_image(self, pil_image, reset=True):
        self.image = pil_image

        if reset:
            self.reset_view()
        else:
            self.redraw()


    def reset_view(self, event=None):
        self.zoom = 1.0
        self.pan_x = 0
        self.pan_y = 0
        self.redraw()

    def start_pan(self, event):
        self.last_x = event.x
        self.last_y = event.y

    def pan(self, event):
        dx = event.x - self.last_x
        dy = event.y - self.last_y
        self.pan_x += dx
        self.pan_y += dy
        self.last_x = event.x
        self.last_y = event.y
        self.redraw()

    def zoom_mouse(self, event):
        factor = 1.1 if event.delta > 0 else 0.9
        self.zoom *= factor
        self.redraw()

    def redraw(self, event=None):
        self.delete("all")

        if self.image is None:
            return

        w, h = self.image.size
        scale = self.zoom

        img = self.image.resize((int(w * scale), int(h * scale)))
        self.tk_image = ImageTk.PhotoImage(img)

        cx = self.winfo_width() // 2 + self.pan_x
        cy = self.winfo_height() // 2 + self.pan_y

        self.create_image(cx, cy, image=self.tk_image)