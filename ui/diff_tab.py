import customtkinter as ctk


class DiffTab(ctk.CTkFrame):

    def __init__(self, master, controller):
        super().__init__(master)

        self.controller = controller

        self.method = ctk.StringVar(value="SSIM")

        self._build_ui()

    def _build_ui(self):
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        top = ctk.CTkFrame(self)
        top.grid(row=0, column=0, sticky="ew")

        ctk.CTkOptionMenu(
            top,
            variable=self.method,
            values=["SSIM", "Diff", "Checkerboard", "Blend"],
        ).pack(side="left", padx=10, pady=10)

        ctk.CTkButton(
            top,
            text="Generate Diff",
            command=self.generate_diff
        ).pack(side="left", padx=10)

        # Canvas
        from ui.zoom_canvas import ZoomPanCanvas
        self.canvas = ZoomPanCanvas(self)
        self.canvas.grid(row=1, column=0, sticky="nsew")

    def generate_diff(self):
        rel = self.controller.current_file

        diff_img, metrics = self.controller.diff_engine.compute(
            rel,
            method=self.method.get()
            )

        self.canvas.set_image(diff_img)

        print(metrics)

        self.canvas.set_image(diff_img)