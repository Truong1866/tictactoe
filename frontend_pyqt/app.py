import sys
import os
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QMessageBox, QWidget,
    QVBoxLayout, QHBoxLayout, QPushButton, QLabel
)
from PyQt6.QtGui import QPainter, QPen, QBrush, QColor
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QPoint

# Thêm đường dẫn thư mục gốc vào sys.path để import các module `core` và `stats_tracker`
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.engine import GomokuEngine
from stats_tracker import StatsTracker  # Đã sửa tên class cho phù hợp với chuẩn

BOARD_SIZE = 15
CELL_SIZE = 40
MARGIN = 30


class AIWorker(QThread):
    """
    Luồng (Thread) riêng biệt để AI tính toán, tránh làm đơ giao diện (Not Responding).
    """
    # Signal trả về (move_index, depth)
    move_ready = pyqtSignal(int, int)

    def __init__(self, engine):
        super().__init__()
        self.engine = engine

    def run(self):
        # Gọi hàm lấy nước đi tốt nhất từ engine, giả định trả về (best_move, depth)
        best_move, depth = self.engine.get_best_move()
        self.move_ready.emit(best_move, depth)


class GomokuBoardWidget(QWidget):
    def __init__(self, engine, stats_tracker, status_label, parent=None):
        super().__init__(parent)
        self.setMinimumSize(BOARD_SIZE * CELL_SIZE + MARGIN * 2, BOARD_SIZE * CELL_SIZE + MARGIN * 2)

        self.engine = engine
        self.stats = stats_tracker
        self.status_label = status_label

        self.ai_worker = None
        self.game_over = False

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Vẽ màu nền bàn cờ (màu gỗ)
        painter.fillRect(self.rect(), QColor("#eDCB76"))

        # Vẽ lưới bàn cờ
        pen = QPen(Qt.GlobalColor.black, 1)
        painter.setPen(pen)
        for i in range(BOARD_SIZE):
            # Đường ngang
            painter.drawLine(MARGIN, MARGIN + i * CELL_SIZE,
                             MARGIN + (BOARD_SIZE - 1) * CELL_SIZE, MARGIN + i * CELL_SIZE)
            # Đường dọc
            painter.drawLine(MARGIN + i * CELL_SIZE, MARGIN,
                             MARGIN + i * CELL_SIZE, MARGIN + (BOARD_SIZE - 1) * CELL_SIZE)

        # Vẽ quân cờ (1D array)
        # Giả định dữ liệu bàn cờ nằm trong engine.board.state hoặc engine.board.grid (mảng 1D)
        # Quân cờ: 0 (trống), 1 (Người/Đen), -1 hoặc 2 (AI/Trắng)
        for row in range(BOARD_SIZE):
            for col in range(BOARD_SIZE):
                idx = row * BOARD_SIZE + col

                # Gọi trực tiếp trạng thái trên board
                piece = self.engine.board.state[
                    idx]  # <-- Chỉnh 'state' thành thuộc tính mảng 1D tương ứng trong file board.py của bạn

                if piece != 0:
                    color = Qt.GlobalColor.black if piece == 1 else Qt.GlobalColor.white
                    painter.setBrush(QBrush(color))
                    # Tâm của quân cờ
                    center_x = MARGIN + col * CELL_SIZE
                    center_y = MARGIN + row * CELL_SIZE
                    painter.drawEllipse(QPoint(center_x, center_y), CELL_SIZE // 2 - 2, CELL_SIZE // 2 - 2)

    def mousePressEvent(self, event):
        if self.game_over or (self.ai_worker and self.ai_worker.isRunning()):
            return

        # Chuyển đổi toạ độ click chuột sang toạ độ lưới grid
        col = round((event.position().x() - MARGIN) / CELL_SIZE)
        row = round((event.position().y() - MARGIN) / CELL_SIZE)

        if 0 <= col < BOARD_SIZE and 0 <= row < BOARD_SIZE:
            idx = row * BOARD_SIZE + col

            # Giả định hàm kiểm tra nước đi hợp lệ
            if self.engine.is_valid_move(idx):
                self.engine.play_move(idx, 1)  # 1: Quân của người chơi
                self.update()

                if self.check_winner(idx):
                    return

                self.trigger_ai()

    def trigger_ai(self):
        self.status_label.setText("Trạng thái: AI đang suy nghĩ (PVS & Heuristics)...")
        self.ai_worker = AIWorker(self.engine)
        self.ai_worker.move_ready.connect(self.handle_ai_move)
        self.ai_worker.start()

    def handle_ai_move(self, move_idx, depth_reached):
        # AI thực hiện nước đi (Giả định quân AI là -1 hoặc 2, tùy cấu hình của bạn)
        # Trong kiến trúc Minimax thường quy định Player 1 là Max, Player -1 là Min
        self.engine.play_move(move_idx, -1)
        self.update()

        # Ghi nhận log theo yêu cầu
        self.stats.log_depth(depth_reached)
        avg_depth = self.stats.get_average_depth()

        print(
            f"[AI INFO] AI đánh ở chỉ số {move_idx}. Độ sâu tìm kiếm: {depth_reached} | Độ sâu trung bình (toàn cục): {avg_depth:.2f}")
        self.status_label.setText(f"Trạng thái: Tới lượt bạn. (Avg Depth: {avg_depth:.2f})")

        self.check_winner(move_idx)

    def check_winner(self, move_idx):
        # Giả định hàm check_win trả về True/False dựa vào nước đi vừa rồi
        winner = self.engine.check_win(move_idx)
        if winner:
            self.game_over = True

            # Lấy xem ô cuối cùng là của ai để xác định người chiến thắng
            last_piece = self.engine.board.state[move_idx]
            msg = "Bạn (Quân Đen) đã giành chiến thắng!" if last_piece == 1 else "AI (Quân Trắng) đã giành chiến thắng!"

            self.status_label.setText("Trạng thái: Trò chơi kết thúc.")
            QMessageBox.information(self, "Kết thúc", msg)
            return True
        return False

    def reset_game(self):
        self.engine.reset()
        self.game_over = False
        self.status_label.setText("Trạng thái: Bắt đầu game mới. Lượt của bạn (Đen).")
        self.update()


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Gomoku AI - Incremental Update & PVS")

        # Khởi tạo Lõi AI và module Thống kê
        self.engine = GomokuEngine()
        self.stats_tracker = StatsTracker("depth_history.json")

        # Thiết lập giao diện
        self.init_ui()

    def init_ui(self):
        main_widget = QWidget()
        layout = QVBoxLayout()

        self.status_label = QLabel("Trạng thái: Tới lượt bạn (Quân Đen).")
        self.status_label.setStyleSheet("font-size: 14px; font-weight: bold; margin-bottom: 10px;")

        self.board_widget = GomokuBoardWidget(self.engine, self.stats_tracker, self.status_label)

        btn_layout = QHBoxLayout()
        reset_btn = QPushButton("Chơi lại (Reset)")
        reset_btn.setFixedSize(150, 40)
        reset_btn.clicked.connect(self.board_widget.reset_game)
        btn_layout.addWidget(reset_btn)

        layout.addWidget(self.status_label)
        layout.addWidget(self.board_widget)
        layout.addLayout(btn_layout)

        main_widget.setLayout(layout)
        self.setCentralWidget(main_widget)

        # Cố định size của sổ để không bị móp méo bàn cờ
        self.setFixedSize(layout.sizeHint())


if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())