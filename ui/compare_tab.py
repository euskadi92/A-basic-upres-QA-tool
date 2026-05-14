import customtkinter as ctk
from PIL import Image
import numpy as np



class CompareTab(ctk.CTkFrame):

    def __init__(self, master, controller):
        super().__init__(master)

        self.controller = controller

        self.compare_mode = ctk.StringVar(value="Toggle")
        self.slider_value = ctk.DoubleVar(value=0.5)
        
        self.diff_cache = {}


        self._build_ui()

    def _build_ui(self):
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(2, weight=1)

        # Sidebar
        sidebar = ctk.CTkFrame(self, width=300)
        sidebar.grid(row=2, column=0, sticky="ns")
        # VIEWER MODE BUTTONS
        self.diff_label = ctk.CTkLabel(sidebar, text="--- VIEWER MODE ---", text_color="#246AD3")
        self.diff_label.pack(padx=10, pady=(20,0), anchor="center")
        self.mode_selector = ctk.CTkSegmentedButton(
            sidebar,
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
        self.slider.pack(padx=10, pady=10, fill="x")

        # NAVIGATION BUTTONS
        self.diff_label = ctk.CTkLabel(sidebar, text="--- IMAGE NAVIGATION ---", text_color="#1FAF3F")
        self.diff_label.pack(padx=10, pady=(20,0), anchor="center")

        nav_frame = ctk.CTkFrame(sidebar)
        nav_frame.pack(padx=10, pady=10, fill="x")

        ctk.CTkButton(
            nav_frame,
            text="Previous",
            command=self.controller.prev_image,
            fg_color="#1FAF3F",
        ).pack(side="left", expand=True, fill="x", padx=(0, 5))

        ctk.CTkButton(
            nav_frame,
            text="Next",
            command=self.controller.next_image,
            fg_color="#1FAF3F",
        ).pack(side="right", expand=True, fill="x", padx=(5, 0))

        self.diff_opacity = ctk.DoubleVar(value=0.5)

        # DIFF OPACITY BUTTONS
        self.diff_label = ctk.CTkLabel(sidebar, text="--- DIFF OVERLAY OPACITY ---", text_color="#99531a")
        self.diff_label.pack(padx=10, pady=(20,0), anchor="center")
        self.diff_slider = ctk.CTkSlider(
            sidebar,
            from_=0.0,
            to=1.0,
            variable=self.diff_opacity,
            button_color="#ff841f",
            button_hover_color="#99531a",
            command=lambda x: self.update_view()
        )

        self.diff_slider.pack(padx=10, pady=5, fill="x")

        

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
            elif view == "output":
                img = self.output
                source = "Output"
            elif view == "diff":
                img = self.diff_cache
                source = "Output + Diff Overlay"
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

            elif self.controller.current_view == "diff":
                img = self.get_overlay_diff()


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


    def get_overlay_diff(self):
        file = self.controller.current_file

        # base output image (what user sees)
        base = self.output

        # get diff image (heatmap)
        diff_img = self.get_diff_image()

        # resize diff to match base (safety)
        if diff_img.size != base.size:
            diff_img = diff_img.resize(base.size)

        # convert to arrays
        base_np = np.array(base).astype(np.float32)
        diff_np = np.array(diff_img).astype(np.float32)

        alpha = self.diff_opacity.get()

        # blend
        blended = (1 - alpha) * base_np + alpha * diff_np

        return Image.fromarray(blended.astype(np.uint8))


    def get_diff_image(self):
        file = self.controller.current_file

        # Use cache
        if file in self.diff_cache:
            return self.diff_cache[file]

        # Compute diff
        diff_img, _ = self.controller.diff_engine.compute(
            file,
            method="SSIM",   # or read from a global setting later
            resample=self.controller.get_resample_filter()
        )

        self.diff_cache[file] = diff_img
        return diff_img
