import customtkinter as ctk
from ui.compare_tab import CompareTab
from ui.diff_tab import DiffTab
from pathlib import Path
from PIL import Image


class ImageCompareApp(ctk.CTk):

    def __init__(self):
        super().__init__()

        self.title("Image Comparator")
        self.geometry("1400x900")

        self.current_view = "input"
        self.current_file = None

        self.gt_dir = Path("ground-truth")
        self.out_dir = Path("output")

        self._build_ui()

    def _build_ui(self):
        self.tabs = ctk.CTkTabview(self)
        self.tabs.pack(fill="both", expand=True)

        # Load each tab
        compare_frame = self.tabs.add("Compare")
        self.compare_tab = CompareTab(compare_frame, self)
        self.compare_tab.pack(fill="both", expand=True)
        
        diff_frame = self.tabs.add("Diff")
        self.diff_tab = DiffTab(diff_frame, self)
        self.diff_tab.pack(fill="both", expand=True)

        self.load_first_image()

        self.bind("<Key>", self.handle_keys)

    def load_first_image(self):
        files = list(self.gt_dir.glob("*"))
        if not files:
            return

        self.current_file = files[0].name

        self.load_current()

    def load_current(self):
        input_img = Image.open(self.gt_dir / self.current_file)
        output_img = Image.open(self.out_dir / self.current_file)

        self.compare_tab.load_images(input_img, output_img)

    def handle_keys(self, event):
        key = event.keysym.lower()

        if key == "i":
            self.current_view = "input"
        elif key == "o":
            self.current_view = "output"
        elif key == "space":
            self.compare_tab.canvas.reset_view()

        self.compare_tab.update_view()
