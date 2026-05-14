import customtkinter as ctk
from ui.compare_tab import CompareTab
from ui.diff_tab import DiffTab
from pathlib import Path
from PIL import Image
from core.image_loader import discover_images
from core.diff_engine import DiffEngine
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

        self.diff_engine = DiffEngine(self.gt_dir, self.out_dir)


        self._build_ui()

    def _build_ui(self):
        self.tabs = ctk.CTkTabview(self)
        self.tabs.pack(fill="both", expand=True)

        # Load each tab
        compare_frame = self.tabs.add("Compare")
        self.compare_tab = CompareTab(compare_frame, self)
        self.compare_tab.pack(fill="both", expand=True)
        
        # diff_frame = self.tabs.add("Diff")
        # self.diff_tab = DiffTab(diff_frame, self)
        # self.diff_tab.pack(fill="both", expand=True)

        self.load_first_image()

        self.bind_all("<Key>", self.handle_keys)

    
    def get_resample_filter(self):
        # will maybe add this with a dropdown, I will see
        return Image.LANCZOS


    def load_first_image(self):
        # Discover files in both folders
        self.gt_files = discover_images(self.gt_dir, {".png", ".jpg", ".jpeg"})
        self.out_files = discover_images(self.out_dir, {".png", ".jpg", ".jpeg"})

        # Find matching files
        common = sorted(set(self.gt_files.keys()) & set(self.out_files.keys()))

        if not common:
            print("No matching images found")
            return

        # ✅ THIS is where file_list is defined
        self.file_list = common

        # Start at first image
        self.current_file = self.file_list[0]
        self.load_current()

    def load_current(self):
        input_img = Image.open(self.gt_dir / self.current_file)
        output_img = Image.open(self.out_dir / self.current_file)

        self.compare_tab.load_images(input_img, output_img)

    def next_image(self):
        current_index = self.file_list.index(self.current_file)
        self.current_file = self.file_list[(current_index + 1) % len(self.file_list)]
        self.load_current()

    def prev_image(self):
        current_index = self.file_list.index(self.current_file)
        self.current_file = self.file_list[(current_index - 1) % len(self.file_list)]
        self.load_current()

    def handle_keys(self, event):
        key = event.keysym.lower()

        if key == "i":
            self.current_view = "input"
        elif key == "o":
            self.current_view = "output"
        elif key == "space":
            self.compare_tab.canvas.reset_view()
        elif key == "p":
            self.current_view = "diff"


        elif key == "left":
            self.prev_image()
        elif key == "right":
            self.next_image()


        self.compare_tab.update_view()
        
        return "break"

