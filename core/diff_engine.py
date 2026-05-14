import numpy as np
from PIL import Image
from skimage.metrics import structural_similarity
from skimage.util import compare_images
from skimage.color import rgb2gray
from skimage import img_as_float, exposure
from matplotlib import cm


class DiffEngine:

    def __init__(self, gt_dir, out_dir):
        self.gt_dir = gt_dir
        self.out_dir = out_dir

    def load_image(self, path):
        img = Image.open(path).convert("RGB")
        arr = np.array(img)
        gray = rgb2gray(arr)
        return img, img_as_float(gray)

    def compute(self, rel_path, method="SSIM", resample=None):
        gt_path = self.gt_dir / rel_path
        out_path = self.out_dir / rel_path

        gt_img, gt_arr = self.load_image(gt_path)
        out_img, out_arr = self.load_image(out_path)
        gt_img = gt_img.resize(out_img.size, resample)
        gt_arr = rgb2gray(np.array(gt_img))


        # Resize ground-truth to match output size
        # if gt_arr.shape != out_arr.shape:
        #     from skimage.transform import resize

        #     gt_arr = resize(
        #         gt_arr,
        #         out_arr.shape,
        #         preserve_range=True,
        #         anti_aliasing=True
        #     )
        gt_img = Image.open(gt_path).convert("RGB")
        out_img = Image.open(out_path).convert("RGB")

        if gt_img.size != out_img.size:
            if resample is None:
                resample = Image.LANCZOS

            gt_img = gt_img.resize(out_img.size, resample)
        

        # --- Metrics ---
        mse = float(np.mean((gt_arr - out_arr) ** 2))
        ssim_score, ssim_map = structural_similarity(
            gt_arr, out_arr, data_range=1.0, full=True
        )

        # --- Diff image ---
        if method == "SSIM":
            diff = 1.0 - ssim_map
            diff = exposure.rescale_intensity(diff, out_range=(0, 1))
            colored = cm.magma(diff)[:, :, :3]
            diff_img = Image.fromarray((colored * 255).astype(np.uint8))

        elif method == "Diff":
            diff = compare_images(gt_arr, out_arr, method="diff")
            diff = exposure.rescale_intensity(diff, out_range=(0, 1))
            colored = cm.magma(diff)[:, :, :3]
            diff_img = Image.fromarray((colored * 255).astype(np.uint8))

        elif method == "Checkerboard":
            comp = compare_images(gt_arr, out_arr, method="checkerboard")
            comp = exposure.rescale_intensity(comp, out_range=(0, 1))
            colored = cm.gray(comp)[:, :, :3]
            diff_img = Image.fromarray((colored * 255).astype(np.uint8))

        elif method == "Blend":
            comp = compare_images(gt_arr, out_arr, method="blend")
            comp = exposure.rescale_intensity(comp, out_range=(0, 1))
            colored = cm.gray(comp)[:, :, :3]
            diff_img = Image.fromarray((colored * 255).astype(np.uint8))

        else:
            raise ValueError(f"Unknown method: {method}")

        # --- Return both ---
        metrics = {
            "file": rel_path,
            "ssim": float(ssim_score),
            "mse": mse,
        }

        return diff_img, metrics