"""
core/types.py
Shared constants, enums và dataclasses cho toàn bộ hệ thống Gomoku AI.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import IntEnum
from typing import Optional


BOARD_SIZE: int = 15
WIN_LENGTH: int = 5
BOARD_CELLS: int = BOARD_SIZE * BOARD_SIZE

# Giá trị ô cờ – dùng IntEnum để so sánh nhanh hơn string
class Cell(IntEnum):
    EMPTY = 0
    BLACK = 1   # AI / player 1
    WHITE = -1  # Human / player 2


# 4 hướng quét (dr, dc): ngang, dọc, chéo chính, chéo phụ
DIRECTIONS: tuple[tuple[int, int], ...] = ((0, 1), (1, 0), (1, 1), (1, -1))

# Chuyển (row, col) → index 1D và ngược lại
def rc_to_idx(row: int, col: int) -> int:
    return row * BOARD_SIZE + col

def idx_to_rc(idx: int) -> tuple[int, int]:
    return divmod(idx, BOARD_SIZE)

def in_bounds(row: int, col: int) -> bool:
    return 0 <= row < BOARD_SIZE and 0 <= col < BOARD_SIZE


@dataclass(frozen=True)
class SearchConfig:
    """Cấu hình tìm kiếm cho một mức độ khó."""
    depth: int = 5
    time_limit_ms: Optional[int] = 1500
    candidate_radius: int = 2
    candidate_limit: int = 20
    use_pvs: bool = True                # Principal Variation Search
    killer_slots: int = 2               # Số killer moves lưu mỗi độ sâu
    threat_extension_depth: int = 1     # Độ sâu mở rộng cho forcing moves


@dataclass
class MoveAnalysis:
    """Kết quả phân tích nước đi từ engine."""
    move: Optional[tuple[int, int]]
    score: float
    reason: str
    completed_depth: int
    nodes_searched: int = 0
    elapsed_ms: float = 0.0
