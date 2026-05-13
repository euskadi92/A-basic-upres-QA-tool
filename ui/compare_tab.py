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
        self.grid_rowconfigure(2, weight=1)

        # Sidebar
        sidebar = ctk.CTkFrame(self, width=300)
        sidebar.grid(row=2, column=0, sticky="ns")

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

        nav_frame = ctk.CTkFrame(sidebar)
        nav_frame.pack(padx=10, pady=10, fill="x")

        ctk.CTkButton(
            nav_frame,
            text="Previous",
            command=self.controller.prev_image
        ).pack(side="left", expand=True, fill="x", padx=(0, 5))

        ctk.CTkButton(
            nav_frame,
            text="Next",
            command=self.controller.next_image
        ).pack(side="right", expand=True, fill="x", padx=(5, 0))

        # Name of the image currently displayed
        self.info_label = ctk.CTkLabel(self, text="", anchor="w")
        self.info_label.grid(row=1, column=1, sticky="ew", padx=10, pady=(0, 5))

        # Canvas
        from ui.zoom_canvas import ZoomPanCanvas
        self.canvas = ZoomPanCanvas(self)
        self.canvas.grid(row=2, column=1, sticky="nsew")

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

    def update_info_label(self):
        file_name = self.controller.current_file
        mode = self.compare_mode.get()
        view = self.controller.current_view

        if mode == "Toggle":
            if view == "input":
                img = self.input
                source = "Ground-truth"
            else:
                img = self.output
                source = "Output"

            width, height = img.size

            text = f"{file_name} | {width} x {height} | {source}"

        else:
            # For side-by-side / overlay → show both
            w1, h1 = self.input.size
            w2, h2 = self.output.size

            text = (
                f"{file_name} | "
                f"Input: {w1}x{h1} | Output: {w2}x{h2} | "
                f"Mode: {mode}"
            )

        self.info_label.configure(text=text)


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

        self.update_info_label()

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