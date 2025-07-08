import sys
import math
from PyQt6.QtWidgets import QApplication, QWidget
from PyQt6.QtGui import QPainter, QColor, QPen
from PyQt6.QtCore import Qt, QTimer


def draw_pixel_lightbar_classic(painter, x, y, width, height, level, max_blocks=8):
    block_height = height // max_blocks
    blocks_to_draw = int(level * max_blocks)

    for i in range(max_blocks):
        block_y = y + height - (i + 1) * block_height
        if i < blocks_to_draw:
            ratio = i / max_blocks
            if ratio < 0.5:
                # green to yellow
                r = int(255 * (ratio * 2))
                g = 255
                b = 0
            else:
                # yellow to red
                r = 255
                g = int(255 * (1 - (ratio - 0.5) * 2))
                b = 0
            color = QColor(r, g, b)
        else:
            color = QColor(30, 30, 30)  # dark/off block

        painter.fillRect(x, block_y, width, block_height - 1, color)


def draw_pixel_lightbar_horizontal(painter, x, y, width, height, level, max_blocks=10):
    block_width = width // max_blocks
    blocks_to_draw = int(level * max_blocks)

    for i in range(max_blocks):
        block_x = x + i * block_width
        if i < blocks_to_draw:
            ratio = i / max_blocks
            r = int(0 + 255 * ratio)
            g = int(128 + 127 * ratio)
            b = 255
            color = QColor(r, g, b)
        else:
            color = QColor(20, 20, 20)

        painter.fillRect(block_x, y, block_width - 2, height, color)


def draw_pixel_lightbar_glow(painter, x, y, width, height, level, max_blocks=12):
    block_height = height // max_blocks
    blocks_to_draw = int(level * max_blocks)

    for i in range(max_blocks):
        block_y = y + height - (i + 1) * block_height

        # Glow behind block
        glow_color = QColor(255, 105, 180, 50)  # pink glow low alpha
        painter.setBrush(glow_color)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRect(x - 2, block_y - 2, width + 4, block_height + 4)

        # Block color
        if i < blocks_to_draw:
            ratio = i / max_blocks
            r = int(128 + 127 * ratio)
            g = 0
            b = int(128 + 127 * (1 - ratio))
            color = QColor(r, g, b)
        else:
            color = QColor(40, 0, 40)

        painter.setBrush(color)
        painter.setPen(QPen(QColor(255, 255, 255), 1))
        painter.drawRect(x, block_y, width, block_height)


class LightbarDemo(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Pixel Style Lightbars Demo")
        self.resize(500, 300)

        self.timer = QTimer()
        self.timer.timeout.connect(self.update_levels)
        self.timer.start(50)  # 20 FPS

        self.time = 0.0
        self.levels = [0.0, 0.0, 0.0]

    def update_levels(self):
        self.time += 0.05
        # Simulated smooth varying audio levels between 0 and 1
        self.levels[0] = (math.sin(self.time * 1.5) + 1) / 2
        self.levels[1] = (math.sin(self.time * 2.3 + 2) + 1) / 2
        self.levels[2] = (math.sin(self.time * 1.1 + 5) + 1) / 2
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)

        # Classic vertical stacked blocks
        draw_pixel_lightbar_classic(painter, 50, 50, 30, 200, self.levels[0])

        # Horizontal vintage bars
        draw_pixel_lightbar_horizontal(painter, 150, 100, 200, 30, self.levels[1])

        # Glow pixel bars with outline
        draw_pixel_lightbar_glow(painter, 400, 50, 30, 200, self.levels[2])


if __name__ == "__main__":
    app = QApplication(sys.argv)
    demo = LightbarDemo()
    demo.show()
    sys.exit(app.exec())
