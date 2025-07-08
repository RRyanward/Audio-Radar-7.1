import sys
import time
import os
import numpy as np
import sounddevice as sd
from scipy.signal import butter, lfilter
from PyQt6.QtWidgets import (QApplication, QWidget, QDialog, QComboBox, QPushButton,
                             QHBoxLayout, QVBoxLayout, QLabel, QSystemTrayIcon, QMenu)
from PyQt6.QtCore import Qt, QTimer, QRect
from PyQt6.QtGui import QPainter, QColor, QIcon, QAction

def resource_path(relative_path):
    """ Get absolute path to resource, works for dev and for PyInstaller """
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

def butter_bandpass(lowcut, highcut, fs, order=4):
    nyq = 0.5 * fs
    b, a = butter(order, [lowcut / nyq, highcut / nyq], btype='band')
    return b, a

def bandpass_filter(data, b, a):
    return lfilter(b, a, data)

class DeviceSelectorPopup(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Select Audio Input Device")
        self.setFixedSize(400, 120)

        self.device_selector = QComboBox()
        self.refresh_button = QPushButton("⟳")
        self.refresh_button.setFixedWidth(30)
        self.apply_button = QPushButton("Apply")
        self.close_button = QPushButton("Close")

        hbox = QHBoxLayout()
        hbox.addWidget(QLabel("Input Device:"))
        hbox.addWidget(self.device_selector)
        hbox.addWidget(self.refresh_button)

        buttons_layout = QHBoxLayout()
        buttons_layout.addWidget(self.apply_button)
        buttons_layout.addWidget(self.close_button)

        vbox = QVBoxLayout()
        vbox.addLayout(hbox)
        vbox.addLayout(buttons_layout)
        self.setLayout(vbox)

        self.refresh_button.clicked.connect(self.populate_devices)
        self.apply_button.clicked.connect(self.apply_settings)
        self.close_button.clicked.connect(self.accept)
        self.device_selector.currentIndexChanged.connect(self.device_changed)

        self.selected_device = None
        self.populate_devices()

    def populate_devices(self):
        self.device_selector.clear()
        devices = sd.query_devices()
        for i, dev in enumerate(devices):
            if dev['max_input_channels'] >= 8:
                self.device_selector.addItem(dev['name'], i)

    def device_changed(self, index):
        self.selected_device = self.device_selector.currentData()

    def get_selected_device(self):
        return self.selected_device

    def apply_settings(self):
        if self.parent() is not None:
            self.parent().update_settings(device=self.get_selected_device())

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
        self.b, self.a = butter_bandpass(500, 1800, self.fs)
        self.selected_device = None
        self.stream = None

        self.channel_colors = [None] * 8
        self.last_trigger_time = [0.0] * 8

        self.prev_levels = [[] for _ in range(8)]
        self.smoothing_window = 3

        self.fade_duration = 1.0  # seconds
        self.hold_time = 0.5      # seconds

        self.GLOBAL_COOLDOWN = 0.5
        self.last_global_trigger = 0

        self.timer = QTimer()
        self.timer.timeout.connect(self.update)
        self.timer.start(30)

        icon_path = resource_path("tray_icon.ico")
        self.tray_icon = QSystemTrayIcon(self)
        if os.path.exists(icon_path):
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
            device = self.device_popup.get_selected_device()
            if device is not None:
                self.selected_device = device
                self.start_audio_stream(device)

    def update_settings(self, device):
        if device != self.selected_device:
            self.selected_device = device
            self.start_audio_stream(device)

    def start_audio_stream(self, device_index):
        if self.stream:
            self.stream.close()
        self.stream = sd.InputStream(device=device_index, channels=8,
                                     samplerate=self.fs, callback=self.audio_callback,
                                     blocksize=1024)
        self.stream.start()

    def audio_callback(self, indata, frames, time_info, status):
        filtered = [bandpass_filter(indata[:, i], self.b, self.a) for i in range(8)]
        levels = [np.sqrt(np.mean(ch**2)) for ch in filtered]

        now = time.time()

        if now - self.last_global_trigger < self.GLOBAL_COOLDOWN:
            return

        for i in range(8):
            self.prev_levels[i].append(levels[i])
            if len(self.prev_levels[i]) > self.smoothing_window:
                self.prev_levels[i].pop(0)

            smoothed = np.mean(self.prev_levels[i])
            max_prev = max(self.prev_levels[i][:-1]) if len(self.prev_levels[i]) > 1 else 0
            delta = levels[i] - smoothed

            if delta > 0.004 and delta > 2.0 * max_prev:
                level = delta * 5
                if level > 0.05:
                    self.channel_colors[i] = QColor(255, 0, 0)  # red
                    self.last_trigger_time[i] = now
                    self.last_global_trigger = now
                    break
                elif level > 0.01:
                    self.channel_colors[i] = QColor(255, 255, 0)  # yellow
                    self.last_trigger_time[i] = now
                    self.last_global_trigger = now
                    break

    def draw_lightbars(self, painter, width, height):
        top_bar_height = 20
        center_bar_width = width // 3
        vertical_bar_width = top_bar_height

        positions = [
            QRect(0, 0, width // 4, top_bar_height),                      # FL
            QRect(3 * width // 4, 0, width // 4, top_bar_height),         # FR
            QRect(width // 3, 0, center_bar_width, top_bar_height),       # C
            QRect(0, height - top_bar_height, width // 4, top_bar_height),          # RL
            QRect(3 * width // 4, height - top_bar_height, width // 4, top_bar_height), # RR
            QRect(0, height // 2 - center_bar_width // 2, vertical_bar_width, center_bar_width),         # SL
            QRect(width - vertical_bar_width, height // 2 - center_bar_width // 2, vertical_bar_width, center_bar_width)  # SR
        ]

        mapping_indices = [0, 1, 2, 4, 5, 6, 7]  # skip LFE

        now = time.time()

        for i, ch_idx in enumerate(mapping_indices):
            color = self.channel_colors[ch_idx]
            triggered = self.last_trigger_time[ch_idx]
            if not color or now - triggered > self.hold_time + self.fade_duration:
                continue

            rect = positions[i]
            alpha = 255

            if now - triggered > self.hold_time:
                fade_progress = (now - triggered - self.hold_time) / self.fade_duration
                alpha = int(255 * (1 - min(fade_progress, 1.0)))

            faded_color = QColor(color.red(), color.green(), color.blue(), alpha)
            painter.fillRect(rect, faded_color)

    def paintEvent(self, event):
        painter = QPainter(self)
        self.draw_lightbars(painter, self.width(), self.height())

if __name__ == '__main__':
    app = QApplication(sys.argv)
    overlay = AudioOverlay()
    overlay.showFullScreen()
    sys.exit(app.exec())
