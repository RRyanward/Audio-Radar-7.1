import sys
import time
import os
import numpy as np
import sounddevice as sd
from scipy.signal import butter, lfilter
from PyQt6.QtWidgets import (QApplication, QWidget, QDialog, QComboBox, QPushButton,
                             QHBoxLayout, QVBoxLayout, QLabel, QSlider, QSystemTrayIcon, QMenu)
from PyQt6.QtCore import Qt, QTimer, QRect
from PyQt6.QtGui import QPainter, QColor, QIcon, QAction

def butter_bandpass(lowcut, highcut, fs, order=4):
    nyq = 0.5 * fs
    b, a = butter(order, [lowcut / nyq, highcut / nyq], btype='band')
    return b, a

def bandpass_filter(data, b, a):
    return lfilter(b, a, data)

def estimate_distance(level, max_level=0.1, min_level=0.0005):
    rms = max(min_level, min(level, max_level))
    dist = max_level / rms
    return max(1.0, min(dist, 20.0))

def interpolate_color(distance, min_dist=1.0, max_dist=20.0):
    d = max(min_dist, min(distance, max_dist))
    t = (max_dist - d) / (max_dist - min_dist)
    r = 255
    g = int(255 * (1 - t))
    b = 0
    alpha = 220
    return QColor(r, g, b, alpha)

class DeviceSelectorPopup(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Select Audio Input Device")
        self.setFixedSize(450, 300)

        self.device_selector = QComboBox()
        self.refresh_button = QPushButton("⟳")
        self.refresh_button.setFixedWidth(30)

        self.slider_label = QLabel("Gain: 100%")
        self.gain_slider = QSlider(Qt.Orientation.Horizontal)
        self.gain_slider.setMinimum(50)
        self.gain_slider.setMaximum(300)
        self.gain_slider.setValue(100)

        self.yellow_label = QLabel("Yellow Threshold: 0.00080")
        self.yellow_slider = QSlider(Qt.Orientation.Horizontal)
        self.yellow_slider.setMinimum(1)
        self.yellow_slider.setMaximum(50)
        self.yellow_slider.setValue(8)

        self.red_label = QLabel("Red Threshold: 0.00250")
        self.red_slider = QSlider(Qt.Orientation.Horizontal)
        self.red_slider.setMinimum(1)
        self.red_slider.setMaximum(50)
        self.red_slider.setValue(25)

        self.apply_button = QPushButton("Apply")
        self.apply_button.clicked.connect(self.apply_settings)

        self.close_button = QPushButton("Close")
        self.close_button.clicked.connect(self.accept)

        hbox = QHBoxLayout()
        hbox.addWidget(QLabel("Input Device:"))
        hbox.addWidget(self.device_selector)
        hbox.addWidget(self.refresh_button)

        buttons_layout = QHBoxLayout()
        buttons_layout.addWidget(self.apply_button)
        buttons_layout.addWidget(self.close_button)

        vbox = QVBoxLayout()
        vbox.addLayout(hbox)
        vbox.addWidget(self.slider_label)
        vbox.addWidget(self.gain_slider)
        vbox.addWidget(self.yellow_label)
        vbox.addWidget(self.yellow_slider)
        vbox.addWidget(self.red_label)
        vbox.addWidget(self.red_slider)
        vbox.addLayout(buttons_layout)

        self.setLayout(vbox)

        self.refresh_button.clicked.connect(self.populate_devices)
        self.device_selector.currentIndexChanged.connect(self.device_changed)
        self.gain_slider.valueChanged.connect(self.gain_moved)
        self.yellow_slider.valueChanged.connect(self.yellow_moved)
        self.red_slider.valueChanged.connect(self.red_moved)

        self.selected_device = None
        self.gain = 1.0
        self.yellow_threshold = 0.0008
        self.red_threshold = 0.0025

        self.populate_devices()

    def populate_devices(self):
        self.device_selector.clear()
        devices = sd.query_devices()
        for i, dev in enumerate(devices):
            if dev['max_input_channels'] >= 8:
                self.device_selector.addItem(dev['name'], i)

    def gain_moved(self, val):
        self.slider_label.setText(f"Gain: {val}%")
        self.gain = val / 100.0

    def yellow_moved(self, val):
        self.yellow_threshold = val / 10000.0
        self.yellow_label.setText(f"Yellow Threshold: {self.yellow_threshold:.5f}")

    def red_moved(self, val):
        self.red_threshold = val / 10000.0
        self.red_label.setText(f"Red Threshold: {self.red_threshold:.5f}")

    def device_changed(self, index):
        self.selected_device = self.device_selector.currentData()

    def get_selected_device(self):
        return self.selected_device

    def get_gain(self):
        return self.gain

    def get_yellow_threshold(self):
        return self.yellow_threshold

    def get_red_threshold(self):
        return self.red_threshold

    def apply_settings(self):
        if self.parent() is not None:
            self.parent().update_settings(
                device=self.get_selected_device(),
                gain=self.get_gain(),
                yellow_threshold=self.get_yellow_threshold(),
                red_threshold=self.get_red_threshold()
            )

class AudioOverlay(QWidget):
    def __init__(self):
        super().__init__()
        screen = QApplication.primaryScreen()
        rect = screen.geometry()
        self.setGeometry(rect)

        self.setWindowFlags(Qt.WindowType.FramelessWindowHint |
                            Qt.WindowType.WindowStaysOnTopHint |
                            Qt.WindowType.Tool)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)

        self.fs = 44100
        self.b, self.a = butter_bandpass(400, 2500, self.fs)
        self.selected_device = None
        self.stream = None

        self.gain = 1.0
        self.yellow_threshold = 0.0008
        self.red_threshold = 0.0025

        self.channel_levels = [0.0] * 8
        self.channel_distances = [20.0] * 8  # start far
        self.prev_levels = [[] for _ in range(8)]
        self.smoothing_window = 3

        self.red_hold_time = 0.5
        self.red_hold_timers = [0] * 8

        self.timer = QTimer()
        self.timer.timeout.connect(self.update)
        self.timer.start(30)

        # Setup tray icon
        icon_path = os.path.join(os.path.dirname(__file__), "tray_icon.ico")
        if not os.path.exists(icon_path):
            icon_path = ""  # fallback if icon missing

        self.tray_icon = QSystemTrayIcon(self)
        if icon_path:
            self.tray_icon.setIcon(QIcon(icon_path))

        tray_menu = QMenu()
        self.toggle_action = QAction("Hide Overlay", self)
        self.toggle_action.triggered.connect(self.toggle_overlay)
        tray_menu.addAction(self.toggle_action)

        change_input_action = QAction("Change Input Device", self)
        change_input_action.triggered.connect(self.show_device_selector_popup)
        tray_menu.addAction(change_input_action)

        exit_action = QAction("Exit", self)
        exit_action.triggered.connect(self.exit_app)
        tray_menu.addAction(exit_action)

        self.tray_icon.setContextMenu(tray_menu)
        self.tray_icon.show()

        self.device_popup = None
        self.show_device_selector_popup()

    def toggle_overlay(self):
        if self.isVisible():
            self.hide()
            self.toggle_action.setText("Show Overlay")
        else:
            self.showFullScreen()
            self.toggle_action.setText("Hide Overlay")

    def exit_app(self):
        if self.stream:
            self.stream.close()
        QApplication.quit()

    def show_device_selector_popup(self):
        self.device_popup = DeviceSelectorPopup(self)
        self.device_popup.exec()
        if self.device_popup:
            new_device = self.device_popup.get_selected_device()
            new_gain = self.device_popup.get_gain()
            new_yt = self.device_popup.get_yellow_threshold()
            new_rt = self.device_popup.get_red_threshold()
            if new_device is not None:
                self.selected_device = new_device
                self.gain = new_gain
                self.yellow_threshold = new_yt
                self.red_threshold = new_rt
                self.start_audio_stream(self.selected_device)

    def update_settings(self, device, gain, yellow_threshold, red_threshold):
        changed_device = (device is not None and device != self.selected_device)
        self.gain = gain
        self.yellow_threshold = yellow_threshold
        self.red_threshold = red_threshold
        if changed_device:
            self.selected_device = device
            self.start_audio_stream(self.selected_device)

    def start_audio_stream(self, device_index):
        if self.stream:
            self.stream.close()
        self.stream = sd.InputStream(device=device_index, channels=8,
                                     samplerate=self.fs, callback=self.audio_callback,
                                     blocksize=1024)
        self.stream.start()

    def audio_callback(self, indata, frames, time_info, status):
        filtered = [bandpass_filter(indata[:, i], self.b, self.a) for i in range(8)]
        levels = [np.sqrt(np.mean(ch**2)) * self.gain for ch in filtered]

        for i in range(8):
            self.prev_levels[i].append(levels[i])
            if len(self.prev_levels[i]) > self.smoothing_window:
                self.prev_levels[i].pop(0)
            level = np.mean(self.prev_levels[i])
            self.channel_levels[i] = level
            self.channel_distances[i] = estimate_distance(level)

            # Hold red brightness for some time after peak
            if level >= self.red_threshold:
                self.red_hold_timers[i] = time.time() + self.red_hold_time

    def draw_lightbars(self, painter, width, height):
        top_bar_height = 20
        center_bar_width = width // 3
        vertical_bar_width = top_bar_height  # 20 px wide vertical bars

        positions = [
            QRect(0, 0, width // 4, top_bar_height),                      # FL - top left horizontal
            QRect(3 * width // 4, 0, width // 4, top_bar_height),         # FR - top right horizontal
            QRect(width // 3, 0, center_bar_width, top_bar_height),       # C - top center horizontal
            # LFE skipped (index 3)
            QRect(0, height - top_bar_height, width // 4, top_bar_height),          # RL - bottom left horizontal
            QRect(3 * width // 4, height - top_bar_height, width // 4, top_bar_height), # RR - bottom right horizontal
            QRect(0, height // 2 - center_bar_width // 2, vertical_bar_width, center_bar_width),         # SL - left vertical tall bar
            QRect(width - vertical_bar_width, height // 2 - center_bar_width // 2, vertical_bar_width, center_bar_width)  # SR - right vertical tall bar
        ]

        mapping_indices = [0, 1, 2, 4, 5, 6, 7]  # skip LFE (3)

        now = time.time()
        for i, ch_idx in enumerate(mapping_indices):
            level = self.channel_levels[ch_idx]
            distance = self.channel_distances[ch_idx]
            rect = positions[i]

            base_color = interpolate_color(distance)

            # Hold red brightness if recently peaked
            if now < self.red_hold_timers[ch_idx]:
                base_color = QColor(255, 0, 0, 255)

            if i in [5, 6]:  # vertical bars (SL, SR)
                fill_length = int(rect.height() * min(level / self.red_threshold, 1.0))
                fill_rect = QRect(rect.x(), rect.y() + rect.height() - fill_length, rect.width(), fill_length)
            else:
                fill_length = int(rect.width() * min(level / self.red_threshold, 1.0))
                fill_rect = QRect(rect.x(), rect.y(), fill_length, rect.height())

            painter.fillRect(fill_rect, base_color)

    def paintEvent(self, event):
        painter = QPainter(self)
        sw, sh = self.width(), self.height()
        self.draw_lightbars(painter, sw, sh)

if __name__ == '__main__':
    app = QApplication(sys.argv)
    overlay = AudioOverlay()
    overlay.showFullScreen()
    sys.exit(app.exec())
