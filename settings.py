from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class Settings:
    base_dir: Path = field(default_factory=lambda: Path(__file__).resolve().parent)
    dll_path: Path = Path("USB3-FRM13_x64.dll")
    model_path: Path = Path("best.pt")
    rgb_calib: Path = Path("undistort_compare/rgb_calibration.npz")
    ir_calib: Path = Path("undistort_compare/ir_calibration.npz")
    homography: Path = Path("homography_result/homography_both.npz")
    ir_baseline: Path = Path("ir_baseline.npy")
    ir_board: int = 0
    rgb_idx: int = 1
    rgb_size: tuple = (640, 480)
    rgb_fps: int = 30
    rgb_delay: float = 0.18
    frame_buf_size: int = 120
    bias_sigma: float = 80.0
    bias_strength: float = 0.88
    safe_margin: int = 3
    common_margin: int = 3
    yolo_conf: float = 0.5
    yolo_imgsz: int = 640
    yolo_device: str | None = None
    yolo_classes: list | None = None
    yolo_fps: float = 5.0
    min_box_area: int = 300
    obj_hot_ir: int = 220
    no_obj_warn_ir: int = 180
    top_percent: float = 5.0
    seat_inner_margin: tuple = (0.25, 0.2)
    obj_inner_margin: tuple = (0.12, 0.12)
    seat_center_margin: int = 18
    use_colormap: bool = True
    rgb_alpha: float = 0.6
    show_height: int = 480
    flask_url: str = "http://127.0.0.1:5000/update_seats"
    send_interval: float = 1.0
