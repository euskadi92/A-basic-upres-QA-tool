import csv
import math
import tkinter as tk
from tkinter import filedialog, messagebox
from pathlib import Path

import customtkinter as ctk
import numpy as np
from PIL import Image, ImageTk

from matplotlib import cm
from skimage import exposure, img_as_float
from skimage.color import rgb2gray, rgba2rgb
from skimage.metrics import structural_similarity
from skimage.transform import resize
from skimage.util import compare_images


SUPPORTED_EXTS = {".png", ".jpg", ".jpeg", ".bmp", ".tif", ".tiff", ".webp"}


# ----------------------------------------------------------------------
# Utilities
# ----------------------------------------------------------------------
def safe_relative_key(path: Path) -> str:
    return path.as_posix()


def ensure_dir(path: Path):
    path.mkdir(parents=True, exist_ok=True)


def pil_from_uint8(arr: np.ndarray) -> Image.Image:
    return Image.fromarray(arr.astype(np.uint8))


def sanitize_output_name(rel_path: str, suffix: str = "", ext: str = ".png") -> str:
    p = Path(rel_path)
    stem = p.stem
    parent = p.parent.as_posix().replace("/", "__")
    if parent and parent != ".":
        return f"{parent}__{stem}{suffix}{ext}"
    return f"{stem}{suffix}{ext}"


# ----------------------------------------------------------------------
# Zoom / Pan Canvas
# ----------------------------------------------------------------------
class ZoomPanCanvas(tk.Canvas):
    def __init__(self, master, bg="#1f1f1f", **kwargs):
        super().__init__(master, bg=bg, highlightthickness=0, **kwargs)

        self.original_pil = None
        self.tk_img = None

        self.base_scale = 1.0
        self.zoom = 1.0
        self.pan_x = 0
        self.pan_y = 0

        self.last_drag_x = None
        self.last_drag_y = None

        self.bind("<Configure>", self._on_resize)
        self.bind("<ButtonPress-1>", self._on_drag_start)
        self.bind("<B1-Motion>", self._on_drag_move)
        self.bind("<Double-Button-1>", self.reset_view)

        # Windows / macOS wheel
        self.bind("<MouseWheel>", self._on_mousewheel)
        # Linux wheel
        self.bind("<Button-4>", self._on_mousewheel_linux_up)
        self.bind("<Button-5>", self._on_mousewheel_linux_down)

    def set_image(self, pil_img: Image.Image):
        self.original_pil = pil_img
        self.reset_view()

    def reset_view(self, event=None):
        self.zoom = 1.0
        self.pan_x = 0
        self.pan_y = 0
        self._compute_base_scale()
        self.redraw()

    def _compute_base_scale(self):
        if self.original_pil is None:
            self.base_scale = 1.0
            return

        cw = max(self.winfo_width(), 1)
        ch = max(self.winfo_height(), 1)
        iw, ih = self.original_pil.size

        self.base_scale = min(cw / iw, ch / ih)

    def _on_resize(self, event=None):
        self._compute_base_scale()
        self.redraw()

    def _on_drag_start(self, event):
        self.last_drag_x = event.x
        self.last_drag_y = event.y

    def _on_drag_move(self, event):
        if self.last_drag_x is None or self.last_drag_y is None:
            return
        dx = event.x - self.last_drag_x
        dy = event.y - self.last_drag_y
        self.pan_x += dx
        self.pan_y += dy
        self.last_drag_x = event.x
        self.last_drag_y = event.y
        self.redraw()

    def _zoom_at(self, factor, x=None, y=None):
        if self.original_pil is None:
            return

        old_zoom = self.zoom
        self.zoom = max(0.1, min(15.0, self.zoom * factor))
        if abs(self.zoom - old_zoom) < 1e-9:
            return
        self.redraw()

    def _on_mousewheel(self, event):
        factor = 1.1 if event.delta > 0 else 1 / 1.1
        self._zoom_at(factor, event.x, event.y)

    def _on_mousewheel_linux_up(self, event):
        self._zoom_at(1.1, event.x, event.y)

    def _on_mousewheel_linux_down(self, event):
        self._zoom_at(1 / 1.1, event.x, event.y)

    def redraw(self):
        self.delete("all")
        if self.original_pil is None:
            return

        iw, ih = self.original_pil.size
        scale = self.base_scale * self.zoom
        draw_w = max(1, int(iw * scale))
        draw_h = max(1, int(ih * scale))

        resized = self.original_pil.resize((draw_w, draw_h), Image.LANCZOS)
        self.tk_img = ImageTk.PhotoImage(resized)

        cx = self.winfo_width() // 2 + self.pan_x
        cy = self.winfo_height() // 2 + self.pan_y

        self.create_image(cx, cy, image=self.tk_img, anchor="center")


# ----------------------------------------------------------------------
# Main App
# ----------------------------------------------------------------------
class ImageCompareApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        ctk.set_appearance_mode("System")
        ctk.set_default_color_theme("blue")

        self.title("Ground Truth vs Output Comparator — V2")
        self.geometry("1550x980")
        self.minsize(1280, 800)

        self.gt_dir = tk.StringVar(value=str(Path.cwd() / "ground-truth"))
        self.out_dir = tk.StringVar(value=str(Path.cwd() / "output"))

        self.common_files = []
        self.gt_files = {}
        self.out_files = {}

        self.current_index = 0
        self.current_view = "input"  # input / output
        self.compare_mode = tk.StringVar(value="Toggle")
        self.diff_method = tk.StringVar(value="SSIM heatmap")
        self.size_mode = tk.StringVar(value="Resize output to input")
        self.sync_selection = tk.BooleanVar(value=True)

        self.overlay_pos = tk.DoubleVar(value=0.5)

        self.compare_base_input = None
        self.compare_base_output = None
        self.compare_rendered = None

        self.diff_rendered = None
        self.last_diff_pil = None

        self.file_buttons = []

        self._build_ui()
        self._bind_keys()
        self.refresh_file_list()

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------
    def _build_ui(self):
        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=1)

        top = ctk.CTkFrame(self, corner_radius=16)
        top.grid(row=0, column=0, sticky="ew", padx=12, pady=12)
        top.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(top, text="Ground-truth folder").grid(row=0, column=0, padx=12, pady=(12, 6), sticky="w")
        ctk.CTkEntry(top, textvariable=self.gt_dir, height=34).grid(row=0, column=1, padx=12, pady=(12, 6), sticky="ew")
        ctk.CTkButton(top, text="Browse", width=90, command=self.browse_gt).grid(row=0, column=2, padx=(0, 12), pady=(12, 6))

        ctk.CTkLabel(top, text="Output folder").grid(row=1, column=0, padx=12, pady=(6, 12), sticky="w")
        ctk.CTkEntry(top, textvariable=self.out_dir, height=34).grid(row=1, column=1, padx=12, pady=(6, 12), sticky="ew")
        ctk.CTkButton(top, text="Browse", width=90, command=self.browse_out).grid(row=1, column=2, padx=(0, 12), pady=(6, 12))

        ctk.CTkButton(top, text="Refresh", width=110, command=self.refresh_file_list).grid(
            row=0, column=3, rowspan=2, padx=(0, 12), pady=12, sticky="ns"
        )

        self.tabs = ctk.CTkTabview(self, corner_radius=18)
        self.tabs.grid(row=1, column=0, sticky="nsew", padx=12, pady=(0, 12))

        self.compare_tab = self.tabs.add("Compare")
        self.diff_tab = self.tabs.add("Diff Map")

        self._build_compare_tab()
        self._build_diff_tab()

        self.status_var = tk.StringVar(value="Ready")
        ctk.CTkLabel(self, textvariable=self.status_var, anchor="w", height=28).grid(
            row=2, column=0, sticky="ew", padx=12, pady=(0, 12)
        )

    def _build_compare_tab(self):
        self.compare_tab.grid_rowconfigure(0, weight=1)
        self.compare_tab.grid_columnconfigure(1, weight=1)

        # Sidebar
        sidebar = ctk.CTkFrame(self.compare_tab, width=340, corner_radius=16)
        sidebar.grid(row=0, column=0, sticky="nsw", padx=(10, 8), pady=10)
        sidebar.grid_rowconfigure(3, weight=1)

        ctk.CTkLabel(sidebar, text="Matching files", font=ctk.CTkFont(size=17, weight="bold")).grid(
            row=0, column=0, padx=12, pady=(12, 8), sticky="w"
        )

        self.compare_mode_seg = ctk.CTkSegmentedButton(
            sidebar,
            values=["Toggle", "Side by side", "Overlay wipe"],
            variable=self.compare_mode,
            command=lambda _: self.refresh_compare_view()
        )
        self.compare_mode_seg.grid(row=1, column=0, padx=12, pady=(0, 10), sticky="ew")

        self.file_scroll = ctk.CTkScrollableFrame(sidebar, corner_radius=12)
        self.file_scroll.grid(row=3, column=0, padx=12, pady=0, sticky="nsew")

        nav_row = ctk.CTkFrame(sidebar, fg_color="transparent")
        nav_row.grid(row=4, column=0, padx=12, pady=12, sticky="ew")
        nav_row.grid_columnconfigure((0, 1), weight=1)

        ctk.CTkButton(nav_row, text="Previous", command=self.prev_image).grid(row=0, column=0, padx=(0, 6), sticky="ew")
        ctk.CTkButton(nav_row, text="Next", command=self.next_image).grid(row=0, column=1, padx=(6, 0), sticky="ew")

        self.overlay_slider = ctk.CTkSlider(
            sidebar,
            from_=0.0,
            to=1.0,
            variable=self.overlay_pos,
            command=lambda _: self.refresh_compare_view()
        )
        self.overlay_slider.grid(row=5, column=0, padx=12, pady=(0, 6), sticky="ew")
        self.overlay_label = ctk.CTkLabel(sidebar, text="Overlay wipe position")
        self.overlay_label.grid(row=6, column=0, padx=12, pady=(0, 12), sticky="w")

        ctk.CTkLabel(
            sidebar,
            text=(
                "Shortcuts\n"
                "I = input\n"
                "O = output\n"
                "← / → = previous / next\n"
                "1 = Toggle\n"
                "2 = Side by side\n"
                "3 = Overlay wipe\n"
                "Mouse wheel = zoom\n"
                "Drag = pan\n"
                "Double-click = reset view"
            ),
            justify="left"
        ).grid(row=7, column=0, padx=12, pady=(0, 12), sticky="w")

        # Main view
        main = ctk.CTkFrame(self.compare_tab, corner_radius=16)
        main.grid(row=0, column=1, sticky="nsew", padx=(8, 10), pady=10)
        main.grid_rowconfigure(2, weight=1)
        main.grid_columnconfigure(0, weight=1)

        self.compare_title_var = tk.StringVar(value="No image loaded")
        self.compare_meta_var = tk.StringVar(value="")

        ctk.CTkLabel(main, textvariable=self.compare_title_var, font=ctk.CTkFont(size=20, weight="bold")).grid(
            row=0, column=0, padx=14, pady=(12, 2), sticky="w"
        )
        ctk.CTkLabel(main, textvariable=self.compare_meta_var, anchor="w").grid(
            row=1, column=0, padx=14, pady=(0, 8), sticky="ew"
        )

        canvas_wrap = ctk.CTkFrame(main, corner_radius=12)
        canvas_wrap.grid(row=2, column=0, padx=14, pady=(0, 14), sticky="nsew")
        canvas_wrap.grid_rowconfigure(0, weight=1)
        canvas_wrap.grid_columnconfigure(0, weight=1)

        self.compare_canvas = ZoomPanCanvas(canvas_wrap)
        self.compare_canvas.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)

    def _build_diff_tab(self):
        self.diff_tab.grid_rowconfigure(1, weight=1)
        self.diff_tab.grid_columnconfigure(0, weight=1)

        controls = ctk.CTkFrame(self.diff_tab, corner_radius=16)
        controls.grid(row=0, column=0, sticky="ew", padx=10, pady=10)
        controls.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(controls, text="Image").grid(row=0, column=0, padx=(12, 8), pady=(12, 6), sticky="w")
        self.diff_image_combo = ctk.CTkComboBox(controls, values=[], command=self.on_diff_file_changed)
        self.diff_image_combo.grid(row=0, column=1, padx=(0, 12), pady=(12, 6), sticky="ew")

        ctk.CTkLabel(controls, text="Method").grid(row=0, column=2, padx=(0, 8), pady=(12, 6), sticky="w")
        ctk.CTkOptionMenu(
            controls,
            variable=self.diff_method,
            values=["SSIM heatmap", "Absolute diff", "Checkerboard", "Blend"]
        ).grid(row=0, column=3, padx=(0, 12), pady=(12, 6), sticky="w")

        ctk.CTkLabel(controls, text="Size handling").grid(row=1, column=0, padx=(12, 8), pady=(6, 12), sticky="w")
        ctk.CTkOptionMenu(
            controls,
            variable=self.size_mode,
            values=[
                "Resize output to input",
                "Resize input to output",
                "None (require same size)",
            ]
        ).grid(row=1, column=1, padx=(0, 12), pady=(6, 12), sticky="w")

        ctk.CTkSwitch(
            controls,
            text="Sync selection with Compare tab",
            variable=self.sync_selection,
            onvalue=True,
            offvalue=False
        ).grid(row=1, column=2, columnspan=2, padx=(0, 12), pady=(6, 12), sticky="w")

        action_wrap = ctk.CTkFrame(controls, fg_color="transparent")
        action_wrap.grid(row=0, column=4, rowspan=2, padx=(0, 12), pady=12, sticky="e")

        ctk.CTkButton(action_wrap, text="Generate Diff", command=self.generate_diff).pack(fill="x")
        ctk.CTkButton(action_wrap, text="Save Current Diff...", command=self.save_diff).pack(fill="x", pady=(8, 0))
        ctk.CTkButton(action_wrap, text="Batch Export Diffs...", command=self.batch_export_diffs).pack(fill="x", pady=(8, 0))
        ctk.CTkButton(action_wrap, text="Export Metrics CSV...", command=self.export_metrics_csv).pack(fill="x", pady=(8, 0))

        # Diff display
        diff_main = ctk.CTkFrame(self.diff_tab, corner_radius=16)
        diff_main.grid(row=1, column=0, sticky="nsew", padx=10, pady=(0, 10))
        diff_main.grid_rowconfigure(1, weight=1)
        diff_main.grid_columnconfigure(0, weight=1)

        self.diff_info_var = tk.StringVar(value="No diff generated")
        ctk.CTkLabel(diff_main, textvariable=self.diff_info_var, anchor="w").grid(
            row=0, column=0, padx=14, pady=(12, 8), sticky="ew"
        )

        canvas_wrap = ctk.CTkFrame(diff_main, corner_radius=12)
        canvas_wrap.grid(row=1, column=0, padx=14, pady=(0, 14), sticky="nsew")
        canvas_wrap.grid_rowconfigure(0, weight=1)
        canvas_wrap.grid_columnconfigure(0, weight=1)

        self.diff_canvas = ZoomPanCanvas(canvas_wrap)
        self.diff_canvas.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)

    # ------------------------------------------------------------------
    # Key bindings
    # ------------------------------------------------------------------
    def _bind_keys(self):
        self.bind("<Key>", self._handle_keypress)

    def _handle_keypress(self, event):
        key = event.keysym.lower()

        if key == "i":
            self.current_view = "input"
            if self.compare_mode.get() == "Toggle":
                self.refresh_compare_view()
        elif key == "o":
            self.current_view = "output"
            if self.compare_mode.get() == "Toggle":
                self.refresh_compare_view()
        elif key == "left":
            self.prev_image()
        elif key == "right":
            self.next_image()
        elif key == "1":
            self.compare_mode.set("Toggle")
            self.refresh_compare_view()
        elif key == "2":
            self.compare_mode.set("Side by side")
            self.refresh_compare_view()
        elif key == "3":
            self.compare_mode.set("Overlay wipe")
            self.refresh_compare_view()

    # ------------------------------------------------------------------
    # Folder discovery
    # ------------------------------------------------------------------
    def browse_gt(self):
        folder = filedialog.askdirectory(initialdir=self.gt_dir.get() or str(Path.cwd()))
        if folder:
            self.gt_dir.set(folder)

    def browse_out(self):
        folder = filedialog.askdirectory(initialdir=self.out_dir.get() or str(Path.cwd()))
        if folder:
            self.out_dir.set(folder)

    def discover_images(self, folder: Path):
        result = {}
        if not folder.exists() or not folder.is_dir():
            return result

        for p in folder.rglob("*"):
            if p.is_file() and p.suffix.lower() in SUPPORTED_EXTS:
                rel = safe_relative_key(p.relative_to(folder))
                result[rel] = p
        return result

    def refresh_file_list(self):
        gt = Path(self.gt_dir.get())
        out = Path(self.out_dir.get())

        self.gt_files = self.discover_images(gt)
        self.out_files = self.discover_images(out)
        self.common_files = sorted(set(self.gt_files.keys()) & set(self.out_files.keys()))
        self.current_index = 0

        self._rebuild_file_buttons()
        self.diff_image_combo.configure(values=self.common_files if self.common_files else [""])

        if not self.common_files:
            self.compare_title_var.set("No matching images found")
            self.compare_meta_var.set("Both folders must contain the same relative file paths.")
            self.compare_canvas.set_image(None)
            self.diff_canvas.set_image(None)
            self.diff_info_var.set("No diff generated")
            self.status_var.set("No matching files found.")
            return

        self._select_index(0)
        self.status_var.set(f"Loaded {len(self.common_files)} matching image(s).")

    def _rebuild_file_buttons(self):
        for widget in self.file_scroll.winfo_children():
            widget.destroy()

        self.file_buttons = []
        for idx, rel in enumerate(self.common_files):
            btn = ctk.CTkButton(
                self.file_scroll,
                text=rel,
                anchor="w",
                height=32,
                command=lambda i=idx: self._select_index(i)
            )
            btn.pack(fill="x", padx=4, pady=4)
            self.file_buttons.append(btn)

        self._refresh_file_button_states()

    def _refresh_file_button_states(self):
        for i, btn in enumerate(self.file_buttons):
            if i == self.current_index:
                btn.configure(fg_color=("gray75", "gray30"))
            else:
                btn.configure(fg_color=None)

    def _select_index(self, idx: int):
        if not self.common_files:
            return
        self.current_index = max(0, min(idx, len(self.common_files) - 1))
        self._refresh_file_button_states()

        rel = self.common_files[self.current_index]
        if self.sync_selection.get():
            self.diff_image_combo.set(rel)

        self.load_current_images()
        self.refresh_compare_view()

    def current_rel_path(self):
        if not self.common_files:
            return None
        return self.common_files[self.current_index]

    def prev_image(self):
        if not self.common_files:
            return
        self._select_index((self.current_index - 1) % len(self.common_files))

    def next_image(self):
        if not self.common_files:
            return
        self._select_index((self.current_index + 1) % len(self.common_files))

    # ------------------------------------------------------------------
    # Image loading & compare rendering
    # ------------------------------------------------------------------
    def load_current_images(self):
        rel = self.current_rel_path()
        if rel is None:
            return

        gt_path = self.gt_files[rel]
        out_path = self.out_files[rel]

        try:
            self.compare_base_input = Image.open(gt_path).convert("RGB")
            self.compare_base_output = Image.open(out_path).convert("RGB")

            in_size = f"{self.compare_base_input.width}x{self.compare_base_input.height}"
            out_size = f"{self.compare_base_output.width}x{self.compare_base_output.height}"

            self.compare_title_var.set(rel)
            self.compare_meta_var.set(
                f"Input: {gt_path.name} ({in_size})   |   Output: {out_path.name} ({out_size})   |   Mode: {self.compare_mode.get()}"
            )
            self.status_var.set(f"Loaded {rel}")
        except Exception as e:
            messagebox.showerror("Image loading error", str(e))

    def _resize_to_same_height(self, img1: Image.Image, img2: Image.Image):
        h = min(img1.height, img2.height)
        if h <= 0:
            return img1, img2

        w1 = max(1, int(img1.width * (h / img1.height)))
        w2 = max(1, int(img2.width * (h / img2.height)))

        return (
            img1.resize((w1, h), Image.LANCZOS),
            img2.resize((w2, h), Image.LANCZOS),
        )

    def _overlay_wipe_image(self, img1: Image.Image, img2: Image.Image, ratio: float):
        ratio = max(0.0, min(1.0, ratio))
        img1, img2 = self._resize_to_same_height(img1, img2)

        # Bring to same width for wipe
        common_w = min(img1.width, img2.width)
        common_h = min(img1.height, img2.height)

        img1 = img1.resize((common_w, common_h), Image.LANCZOS)
        img2 = img2.resize((common_w, common_h), Image.LANCZOS)

        split_x = int(common_w * ratio)

        canvas = Image.new("RGB", (common_w, common_h))
        canvas.paste(img1.crop((0, 0, split_x, common_h)), (0, 0))
        canvas.paste(img2.crop((split_x, 0, common_w, common_h)), (split_x, 0))

        # draw divider line
        arr = np.array(canvas)
        if 0 <= split_x < common_w:
            arr[:, max(0, split_x - 1):min(common_w, split_x + 1), :] = np.array([255, 255, 255], dtype=np.uint8)
        return Image.fromarray(arr)

    def _side_by_side_image(self, img1: Image.Image, img2: Image.Image):
        img1, img2 = self._resize_to_same_height(img1, img2)
        out = Image.new("RGB", (img1.width + img2.width, max(img1.height, img2.height)))
        out.paste(img1, (0, 0))
        out.paste(img2, (img1.width, 0))
        return out

    def refresh_compare_view(self):
        if self.compare_base_input is None or self.compare_base_output is None:
            return

        mode = self.compare_mode.get()
        img_in = self.compare_base_input
        img_out = self.compare_base_output

        if mode == "Toggle":
            rendered = img_in if self.current_view == "input" else img_out
        elif mode == "Side by side":
            rendered = self._side_by_side_image(img_in, img_out)
        elif mode == "Overlay wipe":
            rendered = self._overlay_wipe_image(img_in, img_out, self.overlay_pos.get())
        else:
            rendered = img_in

        self.compare_rendered = rendered
        rel = self.current_rel_path() or ""
        view_label = self.current_view if mode == "Toggle" else mode
        self.compare_meta_var.set(
            f"Input: {img_in.width}x{img_in.height}   |   Output: {img_out.width}x{img_out.height}   |   View: {view_label}"
        )

        self.compare_canvas.set_image(rendered)

        # Show / hide wipe slider
        if mode == "Overlay wipe":
            self.overlay_slider.grid()
            self.overlay_label.grid()
        else:
            self.overlay_slider.grid_remove()
            self.overlay_label.grid_remove()

        self.status_var.set(f"{rel} — compare mode: {mode}")

    # ------------------------------------------------------------------
    # Diff helpers
    # ------------------------------------------------------------------
    def on_diff_file_changed(self, choice):
        if self.sync_selection.get() and choice in self.common_files:
            self._select_index(self.common_files.index(choice))

    def _load_as_float_gray(self, pil_img: Image.Image):
        arr = np.array(pil_img)

        if arr.ndim == 2:
            return img_as_float(arr)

        if arr.ndim == 3 and arr.shape[2] == 4:
            arr = rgba2rgb(arr)

        if arr.ndim == 3:
            return img_as_float(rgb2gray(arr))

        raise ValueError("Unsupported image array shape.")

    def _match_sizes(self, a, b):
        mode = self.size_mode.get()

        if a.shape == b.shape:
            return a, b, "No resize needed"

        if mode == "None (require same size)":
            raise ValueError(f"Image sizes differ: input={a.shape}, output={b.shape}")

        if mode == "Resize output to input":
            b2 = resize(b, a.shape, preserve_range=True, anti_aliasing=True)
            return a, b2, f"Resized output from {b.shape} to {a.shape}"

        if mode == "Resize input to output":
            a2 = resize(a, b.shape, preserve_range=True, anti_aliasing=True)
            return a2, b, f"Resized input from {a.shape} to {b.shape}"

        return a, b, "No resize rule applied"

    def _compute_for_rel(self, rel: str, method: str):
        gt_img = Image.open(self.gt_files[rel])
        out_img = Image.open(self.out_files[rel])

        gt_arr = self._load_as_float_gray(gt_img)
        out_arr = self._load_as_float_gray(out_img)

        original_input_shape = gt_arr.shape
        original_output_shape = out_arr.shape

        gt_arr, out_arr, resize_msg = self._match_sizes(gt_arr, out_arr)

        mse = float(np.mean((gt_arr - out_arr) ** 2))

        score, ssim_map = structural_similarity(gt_arr, out_arr, data_range=1.0, full=True)

        if method == "SSIM heatmap":
            diff = 1.0 - ssim_map
            diff = exposure.rescale_intensity(diff, in_range="image", out_range=(0, 1))
            color = cm.magma(diff)[:, :, :3]
            diff_uint8 = (color * 255).astype(np.uint8)
            out_pil = Image.fromarray(diff_uint8)

        elif method == "Absolute diff":
            diff = compare_images(gt_arr, out_arr, method="diff")
            diff = exposure.rescale_intensity(diff, in_range="image", out_range=(0, 1))
            color = cm.magma(diff)[:, :, :3]
            diff_uint8 = (color * 255).astype(np.uint8)
            out_pil = Image.fromarray(diff_uint8)

        elif method == "Checkerboard":
            comp = compare_images(gt_arr, out_arr, method="checkerboard")
            comp = exposure.rescale_intensity(comp, in_range="image", out_range=(0, 1))
            diff_uint8 = (cm.gray(comp)[:, :, :3] * 255).astype(np.uint8)
            out_pil = Image.fromarray(diff_uint8)

        elif method == "Blend":
            comp = compare_images(gt_arr, out_arr, method="blend")
            comp = exposure.rescale_intensity(comp, in_range="image", out_range=(0, 1))
            diff_uint8 = (cm.gray(comp)[:, :, :3] * 255).astype(np.uint8)
            out_pil = Image.fromarray(diff_uint8)

        else:
            raise ValueError(f"Unsupported method: {method}")

        info = {
            "file": rel,
            "method": method,
            "input_shape": str(original_input_shape),
            "output_shape": str(original_output_shape),
            "resize_note": resize_msg,
            "ssim": float(score),
            "mse": mse,
        }
        return out_pil, info

    # ------------------------------------------------------------------
    # Diff actions
    # ------------------------------------------------------------------
    def generate_diff(self):
        rel = self.diff_image_combo.get() or self.current_rel_path()
        if not rel:
            messagebox.showwarning("No image selected", "Please select an image first.")
            return

        try:
            out_pil, info = self._compute_for_rel(rel, self.diff_method.get())
            self.last_diff_pil = out_pil
            self.diff_rendered = out_pil

            self.diff_info_var.set(
                f"{info['file']} | Method: {info['method']} | SSIM: {info['ssim']:.6f} | MSE: {info['mse']:.6f} | {info['resize_note']}"
            )
            self.diff_canvas.set_image(out_pil)
            self.status_var.set("Diff generated successfully.")
        except Exception as e:
            messagebox.showerror("Diff generation failed", str(e))

    def save_diff(self):
        if self.last_diff_pil is None:
            messagebox.showwarning("Nothing to save", "Generate a diff first.")
            return

        rel = self.diff_image_combo.get() or "diff"
        suggested = sanitize_output_name(rel, suffix="_diff", ext=".png")

        save_path = filedialog.asksaveasfilename(
            defaultextension=".png",
            initialfile=suggested,
            filetypes=[("PNG image", "*.png"), ("JPEG image", "*.jpg"), ("All files", "*.*")]
        )
        if not save_path:
            return

        try:
            self.last_diff_pil.save(save_path)
            self.status_var.set(f"Saved diff to: {save_path}")
        except Exception as e:
            messagebox.showerror("Save failed", str(e))

    def batch_export_diffs(self):
        if not self.common_files:
            messagebox.showwarning("No files", "No matching files found.")
            return

        out_dir = filedialog.askdirectory(title="Select output folder for batch export")
        if not out_dir:
            return

        out_dir = Path(out_dir)
        ensure_dir(out_dir)

        method = self.diff_method.get()
        exported = 0
        errors = []

        for rel in self.common_files:
            try:
                out_pil, _info = self._compute_for_rel(rel, method)
                export_name = sanitize_output_name(rel, suffix="_diff", ext=".png")
                out_pil.save(out_dir / export_name)
                exported += 1
            except Exception as e:
                errors.append(f"{rel}: {e}")

        msg = f"Exported {exported} diff image(s) to:\n{out_dir}"
        if errors:
            msg += f"\n\nErrors on {len(errors)} file(s):\n" + "\n".join(errors[:10])
            if len(errors) > 10:
                msg += "\n..."

        self.status_var.set(f"Batch export finished. Exported: {exported}")
        messagebox.showinfo("Batch export complete", msg)

    def export_metrics_csv(self):
        if not self.common_files:
            messagebox.showwarning("No files", "No matching files found.")
            return

        save_path = filedialog.asksaveasfilename(
            defaultextension=".csv",
            initialfile="image_metrics.csv",
            filetypes=[("CSV file", "*.csv"), ("All files", "*.*")]
        )
        if not save_path:
            return

        rows = []
        errors = []

        for rel in self.common_files:
            try:
                _out_pil, info = self._compute_for_rel(rel, self.diff_method.get())
                rows.append(info)
            except Exception as e:
                errors.append({"file": rel, "error": str(e)})

        try:
            with open(save_path, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(["file", "method", "input_shape", "output_shape", "resize_note", "ssim", "mse"])
                for row in rows:
                    writer.writerow([
                        row["file"],
                        row["method"],
                        row["input_shape"],
                        row["output_shape"],
                        row["resize_note"],
                        row["ssim"],
                        row["mse"],
                    ])

                if errors:
                    writer.writerow([])
                    writer.writerow(["errors"])
                    writer.writerow(["file", "error"])
                    for err in errors:
                        writer.writerow([err["file"], err["error"]])

            self.status_var.set(f"Metrics CSV saved: {save_path}")
            messagebox.showinfo(
                "CSV export complete",
                f"Saved {len(rows)} metric row(s) to:\n{save_path}" +
                (f"\n\nErrors: {len(errors)}" if errors else "")
            )
        except Exception as e:
            messagebox.showerror("CSV export failed", str(e))


if __name__ == "__main__":
    app = ImageCompareApp()
    app.mainloop()