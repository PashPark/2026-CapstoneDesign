import collections
import ctypes
import threading
import time
from ctypes import POINTER, byref, c_int, c_uint8, c_uint32
import cv2
import numpy as np


class FRM13Camera:
    def __init__(self, dll_path, board_idx=0):
        self.daq = ctypes.CDLL(str(dll_path))
        for name in ("OpenDAQDevice", "CloseDAQDevice"):
            api = getattr(self.daq, name)
            api.argtypes = []
            api.restype = c_int
        for name in ("LVDS_Init_Mul", "LVDS_Start_Mul", "LVDS_Stop_Mul", "LVDS_Close_Mul"):
            api = getattr(self.daq, name)
            api.argtypes = [c_int]
            api.restype = c_int
        self.daq.LVDS_GetFrame_Mul.argtypes = [c_int, POINTER(c_uint32), POINTER(c_uint8)]
        self.daq.LVDS_GetFrame_Mul.restype = c_int
        self.daq.LVDS_GetResolution_Mul.argtypes = [c_int, POINTER(c_uint32), POINTER(c_uint32)]
        self.daq.LVDS_GetResolution_Mul.restype = c_int
        self.daq.LVDS_SetDataMode_Mul.argtypes = [c_int, c_int]
        self.daq.LVDS_SetDataMode_Mul.restype = c_int
        self.board_idx = c_int(board_idx)
        self._started = False
        self._released = False
        n_boards = self.daq.OpenDAQDevice()
        if n_boards <= 0:
            raise RuntimeError(f"[IR] OpenDAQDevice 실패: {n_boards}")
        if not self.daq.LVDS_Init_Mul(self.board_idx):
            self.daq.CloseDAQDevice()
            raise RuntimeError("[IR] LVDS_Init_Mul 실패")
        if not self.daq.LVDS_SetDataMode_Mul(self.board_idx, c_int(1)):
            self.daq.LVDS_Close_Mul(self.board_idx)
            self.daq.CloseDAQDevice()
            raise RuntimeError("[IR] LVDS_SetDataMode_Mul 실패")
        width, height = (c_uint32(), c_uint32())
        if not self.daq.LVDS_GetResolution_Mul(self.board_idx, byref(width), byref(height)):
            raise RuntimeError("[IR] LVDS_GetResolution_Mul 실패")
        self.width, self.height = (width.value, height.value)
        self._buf = np.empty(self.width * self.height, dtype=np.uint16)
        self._ptr = self._buf.ctypes.data_as(POINTER(c_uint8))

    def start(self):
        if self._started:
            return
        if not self.daq.LVDS_Start_Mul(self.board_idx):
            raise RuntimeError("[IR] LVDS_Start_Mul 실패")
        self._started = True

    def read(self):
        count = c_uint32(self._buf.nbytes)
        ok = self.daq.LVDS_GetFrame_Mul(self.board_idx, byref(count), self._ptr)
        if not ok or count.value < self._buf.nbytes:
            return (False, None)
        return (True, self._buf.reshape(self.height, self.width).copy())

    def stop(self):
        if not self._started:
            return
        self.daq.LVDS_Stop_Mul(self.board_idx)
        self._started = False

    def release(self):
        if self._released:
            return
        self._released = True
        try:
            if self._started:
                self.stop()
        finally:
            self.daq.LVDS_Close_Mul(self.board_idx)
            self.daq.CloseDAQDevice()


class OpenCVRGBCamera:
    def __init__(self, cfg):
        self.cap = cv2.VideoCapture(cfg.rgb_idx, cv2.CAP_DSHOW)
        if not self.cap.isOpened():
            raise RuntimeError(f"[RGB] VideoCapture open 실패: index={cfg.rgb_idx}")
        self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        self.cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG"))
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, cfg.rgb_size[0])
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, cfg.rgb_size[1])
        self.cap.set(cv2.CAP_PROP_FPS, cfg.rgb_fps)

    def read(self):
        ok, frame = self.cap.read()
        if not ok or frame is None:
            return (False, None)
        if frame.ndim == 2:
            frame = cv2.cvtColor(frame, cv2.COLOR_GRAY2BGR)
        return (True, frame)

    def release(self):
        if self.cap is not None:
            self.cap.release()
            self.cap = None


class FrameBuffer:
    def __init__(self, maxlen=120):
        self.buffer = collections.deque(maxlen=maxlen)
        self.lock = threading.Lock()

    def push(self, ts, frame):
        with self.lock:
            self.buffer.append((ts, frame))

    def get_latest(self):
        with self.lock:
            if not self.buffer:
                return (None, None)
            ts, frame = self.buffer[-1]
            return (ts, frame.copy())

    def pop_closest_before(self, ts, max_delay=0.5):
        with self.lock:
            for index in range(len(self.buffer) - 1, -1, -1):
                stamp, _ = self.buffer[index]
                if stamp <= ts:
                    if ts - stamp > max_delay:
                        return (None, None)
                    for _ in range(index):
                        self.buffer.popleft()
                    return self.buffer.popleft()
            return (None, None)


def ir_capture_loop(camera, frames, stop_event):
    while not stop_event.is_set():
        ok, frame = camera.read()
        if not ok:
            time.sleep(0.001)
            continue
        frames.push(time.monotonic(), frame)


def rgb_capture_loop(camera, frames, stop_event):
    time.sleep(0.5)
    while not stop_event.is_set():
        ok, frame = camera.read()
        if not ok:
            time.sleep(0.005)
            continue
        frames.push(time.monotonic(), frame)
