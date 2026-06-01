"""
core/board.py
Bàn cờ 1D với Zobrist Hashing tiệm tiến (incremental update).

Thay vì tính hash từ đầu O(N²) sau mỗi nước đi, ta XOR từng ô khi
đặt/thu hồi quân → O(1) mỗi thao tác.
"""
from __future__ import annotations

import random
from typing import Optional

from core.types import (
    BOARD_SIZE, BOARD_CELLS, WIN_LENGTH, Cell, DIRECTIONS,
    rc_to_idx, idx_to_rc, in_bounds, SearchConfig,
)


class ZobristTable:
    """Bảng Zobrist được khởi tạo một lần, dùng chung toàn chương trình."""

    _instance: Optional["ZobristTable"] = None

    def __new__(cls) -> "ZobristTable":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._build()
        return cls._instance

    def _build(self) -> None:
        rng = random.Random(20260408)
        # table[cell_index][stone_type]: stone_type 0=BLACK, 1=WHITE
        self.table: list[list[int]] = [
            [rng.getrandbits(64), rng.getrandbits(64)]
            for _ in range(BOARD_CELLS)
        ]
        # XOR thêm khi đến lượt WHITE để phân biệt transposition
        self.side_key: dict[int, int] = {
            Cell.BLACK: rng.getrandbits(64),
            Cell.WHITE: rng.getrandbits(64),
        }

    def piece_hash(self, idx: int, stone: Cell) -> int:
        """Trả về Zobrist key của quân stone tại ô idx."""
        stone_slot = 0 if stone == Cell.BLACK else 1
        return self.table[idx][stone_slot]


_ZOBRIST = ZobristTable()


class Board:
    """
    Bàn cờ Gomoku 15×15 lưu trữ dưới dạng mảng 1D.

    Ưu điểm so với list-of-lists:
    - Truy cập cache-friendly hơn (một đoạn bộ nhớ liên tục).
    - index = row * BOARD_SIZE + col → tránh double dereference.

    Zobrist hash được cập nhật O(1) sau mỗi make/undo_move.
    """

    __slots__ = ("_cells", "_hash", "_side", "_stone_count", "_last_move")

    def __init__(self) -> None:
        self._cells: list[int] = [Cell.EMPTY] * BOARD_CELLS
        self._hash: int = 0
        self._side: Cell = Cell.BLACK   # Người đi trước (BLACK = AI)
        self._stone_count: int = 0
        self._last_move: Optional[int] = None  # index 1D của nước vừa đánh

    # ------------------------------------------------------------------
    # Truy cập cơ bản
    # ------------------------------------------------------------------

    def get(self, row: int, col: int) -> int:
        return self._cells[rc_to_idx(row, col)]

    def get_idx(self, idx: int) -> int:
        return self._cells[idx]

    def is_empty(self, row: int, col: int) -> bool:
        return self._cells[rc_to_idx(row, col)] == Cell.EMPTY

    def is_empty_idx(self, idx: int) -> bool:
        return self._cells[idx] == Cell.EMPTY

    @property
    def hash(self) -> int:
        """Zobrist hash hiện tại, đã bao gồm side-to-move key."""
        return self._hash ^ _ZOBRIST.side_key[self._side]

    @property
    def side(self) -> Cell:
        return self._side

    @property
    def stone_count(self) -> int:
        return self._stone_count

    @property
    def last_move(self) -> Optional[int]:
        return self._last_move

    def is_full(self) -> bool:
        return self._stone_count == BOARD_CELLS

    # ------------------------------------------------------------------
    # Đặt / thu hồi quân – cập nhật hash O(1)
    # ------------------------------------------------------------------

    def make_move(self, idx: int, stone: Cell) -> None:
        """Đặt quân stone tại ô idx, cập nhật hash tiệm tiến."""
        assert self._cells[idx] == Cell.EMPTY, f"Cell {idx} is not empty"
        self._cells[idx] = stone
        # XOR để thêm quân vào hash
        self._hash ^= _ZOBRIST.piece_hash(idx, stone)
        self._side = Cell.WHITE if stone == Cell.BLACK else Cell.BLACK
        self._stone_count += 1
        self._last_move = idx

    def undo_move(self, idx: int, stone: Cell) -> None:
        """Thu hồi quân stone tại ô idx, cập nhật hash tiệm tiến."""
        assert self._cells[idx] == stone, f"Cell {idx} does not contain expected stone"
        self._cells[idx] = Cell.EMPTY
        # XOR ngược lại để xóa quân khỏi hash (XOR đối xứng)
        self._hash ^= _ZOBRIST.piece_hash(idx, stone)
        self._side = stone  # người vừa đi quay lại lượt
        self._stone_count -= 1

    # ------------------------------------------------------------------
    # Kiểm tra thắng – quét từ điểm vừa đánh
    # ------------------------------------------------------------------

    def has_won(self, idx: int, stone: Cell) -> bool:
        """
        Kiểm tra xem quân stone tại ô idx có tạo thành 5 liên tiếp không.
        Chỉ quét 4 hướng qua điểm đó → nhanh hơn quét toàn bàn.
        """
        row, col = idx_to_rc(idx)
        for dr, dc in DIRECTIONS:
            count = 1
            # Quét theo chiều dương
            r, c = row + dr, col + dc
            while in_bounds(r, c) and self._cells[rc_to_idx(r, c)] == stone:
                count += 1
                r += dr
                c += dc
            # Quét theo chiều âm
            r, c = row - dr, col - dc
            while in_bounds(r, c) and self._cells[rc_to_idx(r, c)] == stone:
                count += 1
                r -= dr
                c -= dc
            if count >= WIN_LENGTH:
                return True
        return False

    def has_winner_for(self, stone: Cell) -> bool:
        """Quét toàn bàn (dùng khi cần kiểm tra trạng thái tùy ý)."""
        for idx in range(BOARD_CELLS):
            if self._cells[idx] != stone:
                continue
            row, col = idx_to_rc(idx)
            for dr, dc in DIRECTIONS:
                if all(
                    in_bounds(row + dr * s, col + dc * s)
                    and self._cells[rc_to_idx(row + dr * s, col + dc * s)] == stone
                    for s in range(WIN_LENGTH)
                ):
                    return True
        return False

    # ------------------------------------------------------------------
    # Export sang format list[list[int]] để tương thích với frontend cũ
    # ------------------------------------------------------------------

    def to_2d(self) -> list[list[int]]:
        return [
            [self._cells[rc_to_idx(r, c)] for c in range(BOARD_SIZE)]
            for r in range(BOARD_SIZE)
        ]

    @classmethod
    def from_2d(cls, grid: list[list[int]]) -> "Board":
        b = cls()
        for r in range(BOARD_SIZE):
            for c in range(BOARD_SIZE):
                v = grid[r][c]
                if v != Cell.EMPTY:
                    idx = rc_to_idx(r, c)
                    stone = Cell.BLACK if v == Cell.BLACK else Cell.WHITE
                    b._cells[idx] = stone
                    b._hash ^= _ZOBRIST.piece_hash(idx, stone)
                    b._stone_count += 1
        return b
