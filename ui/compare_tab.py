import customtkinter as ctk
from PIL import Image


class CompareTab(ctk.CTkFrame):

    def __init__(self, master, controller):
        super().__init__(master)

        self.controller = controller

        self.compare_mode = ctk.StringVar(value="Toggle")
        self.slider_value = ctk.DoubleVar(value=0.5)

        self._build_ui()

    def _build_ui(self):
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # Sidebar
        sidebar = ctk.CTkFrame(self, width=300)
        sidebar.grid(row=0, column=0, sticky="ns")

        self.mode_selector = ctk.CTkSegmentedButton(
            sidebar,
            # values=["Toggle", "Side-by-side", "Overlay"], <-- no need for the side-by-side view
            values=["Toggle", "Overlay"],

            variable=self.compare_mode,
            command=self.update_view
        )
        self.mode_selector.pack(padx=10, pady=10, fill="x")

        self.slider = ctk.CTkSlider(
            sidebar,
            from_=0,
            to=1,
            variable=self.slider_value,
            command=lambda x: self.update_view()
        )
        self.slider.pack(padx=10, pady=5, fill="x")

        # Canvas
        from ui.zoom_canvas import ZoomPanCanvas
        self.canvas = ZoomPanCanvas(self)
        self.canvas.grid(row=0, column=1, sticky="nsew")

    def match_scale(self, input_img, output_img):
        """
        Resize input image (ground-truth) to match output resolution.
        """

        if input_img.size == output_img.size:
            return input_img, output_img

        return (
            input_img.resize(output_img.size, Image.LANCZOS),
            output_img
        )

    def load_images(self, input_img: Image.Image, output_img: Image.Image):
        self.input, self.output = self.match_scale(input_img, output_img)
        self.update_view()

    def update_view(self):
        mode = self.compare_mode.get()

        if mode == "Toggle":
            #img = self.input
            if self.controller.current_view == "input":
                img = self.input

            elif self.controller.current_view == "output":
                img = self.output

        elif mode == "Side-by-side":
            img = self.side_by_side(self.input, self.output)

        else:  # Overlay
            img = self.overlay(self.input, self.output, self.slider_value.get())

        self.canvas.set_image(img, reset=False)

    def side_by_side(self, a, b):
        h = min(a.height, b.height)
        a = a.resize((int(a.width * h / a.height), h))
        b = b.resize((int(b.width * h / b.height), h))

        out = Image.new("RGB", (a.width + b.width, h))
        out.paste(a, (0, 0))
        out.paste(b, (a.width, 0))
        return out

    def overlay(self, a, b, ratio):
        w = min(a.width, b.width)
        h = min(a.height, b.height)

        a = a.resize((w, h))
        b = b.resize((w, h))

        split = int(w * ratio)

        out = Image.new("RGB", (w, h))
        out.paste(a.crop((0, 0, split, h)), (0, 0))
        out.paste(b.crop((split, 0, w, h)), (split, 0))
        return out