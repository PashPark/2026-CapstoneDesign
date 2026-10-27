import cv2
import numpy as np


def largest_valid_rect(mask):
    height, width = mask.shape
    heights = np.zeros(width, dtype=np.int32)
    best_area = 0
    best = (0, 0, 0, 0)
    for y in range(height):
        heights = np.where(mask[y] > 0, heights + 1, 0)
        stack = []
        for x in range(width + 1):
            current = heights[x] if x < width else 0
            start = x
            while stack and stack[-1][1] > current:
                index, bar = stack.pop()
                area = (x - index) * bar
                if area > best_area:
                    best_area = area
                    best = (int(index), int(y - bar + 1), int(x - index), int(bar))
                start = index
            stack.append((start, current))
    return best


def prepare_rgb_size(frame, target_size):
    target_w, target_h = target_size
    h, w = frame.shape[:2]
    target_ratio = target_w / target_h
    if w / h > target_ratio:
        crop_w = int(h * target_ratio)
        left = (w - crop_w) // 2
        frame = frame[:, left : left + crop_w]
    elif w / h < target_ratio:
        crop_h = int(w / target_ratio)
        top = (h - crop_h) // 2
        frame = frame[top : top + crop_h, :]
    if frame.shape[1::-1] != target_size:
        frame = cv2.resize(frame, target_size, interpolation=cv2.INTER_AREA)
    return frame


class Calibration:
    def __init__(self, cfg):
        self.cfg = cfg
        self.maps = {}
        self.sizes = {}
        self.crops = {}
        self.homographies = {}
        for name, rel_path in (("rgb", cfg.rgb_calib), ("ir", cfg.ir_calib)):
            path = cfg.base_dir / rel_path
            if not path.exists():
                raise FileNotFoundError(f"Calibration NPZ 없음:\n{path}")
            with np.load(path) as data:
                cam_mtx = data["camera_matrix"].astype(np.float64)
                dist_coeffs = data["dist_coeffs"].astype(np.float64)
                size = tuple((int(value) for value in data["image_size"]))
            self.sizes[name] = size
            new_cam_mtx, _ = cv2.getOptimalNewCameraMatrix(cam_mtx, dist_coeffs, size, 0, size)
            map_x, map_y = cv2.initUndistortRectifyMap(
                cam_mtx, dist_coeffs, None, new_cam_mtx, size, cv2.CV_32FC1
            )
            valid = (map_x >= 1) & (map_x < size[0] - 2) & (map_y >= 1) & (map_y < size[1] - 2)
            x, y, w, h = largest_valid_rect(valid)
            margin = cfg.safe_margin
            x, y, w, h = (x + margin, y + margin, w - 2 * margin, h - 2 * margin)
            if w <= 0 or h <= 0:
                raise RuntimeError("Undistort crop 영역 오류")
            self.maps[name] = (map_x[y : y + h, x : x + w], map_y[y : y + h, x : x + w])
            self.crops[name] = (w, h)
        path = cfg.base_dir / cfg.homography
        if not path.exists():
            raise FileNotFoundError(f"Homography NPZ 없음:\n{path}")
        with np.load(path) as data:
            self.output_size = tuple((int(value) for value in data["output_size"]))
            for name in ("rgb", "ir"):
                self.homographies[name] = data[f"H_{name}_to_common"].astype(np.float64)
        masks = []
        for name in ("rgb", "ir"):
            w, h = self.crops[name]
            warped = cv2.warpPerspective(
                np.full((h, w), 255, np.uint8),
                self.homographies[name],
                self.output_size,
                flags=cv2.INTER_NEAREST,
                borderMode=cv2.BORDER_CONSTANT,
                borderValue=0,
            )
            masks.append(cv2.erode(warped, np.ones((3, 3), np.uint8), iterations=1))
        x, y, w, h = largest_valid_rect(cv2.bitwise_and(*masks))
        margin = cfg.common_margin
        self.common_bbox = (x + margin, y + margin, w - margin * 2, h - margin * 2)
        if self.common_bbox[2] <= 0 or self.common_bbox[3] <= 0:
            raise RuntimeError("RGB / IR 공통영역 없음")
        path = cfg.base_dir / cfg.ir_baseline
        if not path.exists():
            raise FileNotFoundError(f"IR baseline 파일이 없습니다:\n{path}")
        baseline = np.load(path).astype(np.float32)
        if baseline.shape[::-1] != self.sizes["ir"]:
            baseline = cv2.resize(baseline, self.sizes["ir"], interpolation=cv2.INTER_LINEAR)
        smooth = cv2.GaussianBlur(baseline, (0, 0), cfg.bias_sigma)
        self.bias = (smooth - np.median(smooth)) * cfg.bias_strength

    def align(self, rgb_frame, ir_raw):
        rgb = prepare_rgb_size(rgb_frame, self.sizes["rgb"])
        if ir_raw.shape[1] == 1280:
            ir_raw = ir_raw[:, 0::2]
        if ir_raw.shape[0] == 481:
            ir_raw = ir_raw[:480]
        if ir_raw.shape[1::-1] != self.sizes["ir"]:
            ir_raw = cv2.resize(ir_raw, self.sizes["ir"], interpolation=cv2.INTER_NEAREST)
        corrected = np.clip(np.clip(ir_raw, 0, 255).astype(np.float32) - self.bias, 0, 255).astype(np.uint8)
        aligned = []
        x, y, w, h = self.common_bbox
        for name, image in (("rgb", rgb), ("ir", corrected)):
            undistorted = cv2.remap(
                image,
                *self.maps[name],
                interpolation=cv2.INTER_LINEAR,
                borderMode=cv2.BORDER_CONSTANT,
                borderValue=0,
            )
            warped = cv2.warpPerspective(
                undistorted,
                self.homographies[name],
                self.output_size,
                flags=cv2.INTER_LINEAR,
                borderMode=cv2.BORDER_CONSTANT,
                borderValue=0,
            )
            aligned.append(cv2.rotate(warped[y : y + h, x : x + w], cv2.ROTATE_180))
        return tuple(aligned)
