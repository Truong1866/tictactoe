"""
core/evaluator.py
Đánh giá bàn cờ tiệm tiến (Incremental Evaluation).

Chiến lược:
- Duy trì score tổng thể (điểm BLACK - điểm WHITE).
- Khi đặt / thu hồi quân tại idx, chỉ tính lại điểm của 4 đường
  đi qua idx (hàng, cột, 2 đường chéo) thay vì quét toàn bàn.

Pattern scoring:
- Dựa trên số quân liên tục và số đầu mở (0, 1, 2) trong từng đoạn.
- Threat patterns: five, open_four, closed_four, open_three, broken_three.
"""
from __future__ import annotations

from core.types import (
    BOARD_SIZE, BOARD_CELLS, WIN_LENGTH, Cell, DIRECTIONS,
    rc_to_idx, idx_to_rc, in_bounds,
)
from core.board import Board


# ---------------------------------------------------------------------------
# Bảng điểm cho pattern (count, open_ends)
# ---------------------------------------------------------------------------
_PATTERN_SCORE: dict[tuple[int, int], int] = {
    (5, 0): 2_000_000,
    (4, 2): 150_000,
    (4, 1): 30_000,
    (3, 2): 8_000,
    (3, 1): 800,
    (2, 2): 300,
    (2, 1): 60,
    (1, 2): 10,
}

# Bonus cho double-threat (2+ forcing moves đồng thời)
_DOUBLE_THREAT_BONUS = 60_000


def _score_line(cells: list[int], stone: Cell) -> int:
    """
    Tính điểm cho một đường (line) gồm nhiều ô.
    cells: danh sách giá trị ô (Cell enum) dọc theo đường đó.
    """
    total = 0
    n = len(cells)
    i = 0
    while i < n:
        if cells[i] != stone:
            i += 1
            continue
        # Đếm chuỗi liên tục từ i
        j = i
        while j < n and cells[j] == stone:
            j += 1
        count = j - i

        # Kiểm tra đầu mở
        open_ends = 0
        if i > 0 and cells[i - 1] == Cell.EMPTY:
            open_ends += 1
        if j < n and cells[j] == Cell.EMPTY:
            open_ends += 1

        key = (min(count, 5), open_ends)
        total += _PATTERN_SCORE.get(key, 0)
        i = j
    return total


def _extract_line(board: Board, row: int, col: int, dr: int, dc: int) -> list[int]:
    """Trích xuất toàn bộ đường đi qua (row, col) theo hướng (dr, dc)."""
    # Lùi về điểm đầu đường
    r, c = row, col
    while in_bounds(r - dr, c - dc):
        r -= dr
        c -= dc
    # Thu thập
    cells: list[int] = []
    while in_bounds(r, c):
        cells.append(board.get(r, c))
        r += dr
        c += dc
    return cells


def score_line_for_stone(board: Board, row: int, col: int, dr: int, dc: int, stone: Cell) -> int:
    """Tính điểm của stone trên đường đi qua (row, col)."""
    cells = _extract_line(board, row, col, dr, dc)
    return _score_line(cells, stone)


class IncrementalEvaluator:
    """
    Đánh giá tiệm tiến: duy trì điểm và cập nhật sau mỗi nước đi.

    score > 0: lợi cho BLACK (AI)
    score < 0: lợi cho WHITE (human)
    """

    __slots__ = ("_score",)

    def __init__(self) -> None:
        self._score: int = 0

    # ------------------------------------------------------------------
    # API công khai
    # ------------------------------------------------------------------

    def full_eval(self, board: Board) -> int:
        """Tính toàn bộ điểm từ đầu (dùng để khởi tạo hoặc kiểm tra)."""
        self._score = self._compute_full(board)
        return self._score

    def on_make_move(self, board: Board, idx: int, stone: Cell) -> None:
        """Cập nhật điểm sau khi đặt stone tại idx."""
        self._score -= self._score_around(board, idx, stone, before=True)
        self._score += self._score_around(board, idx, stone, before=False)

    def on_undo_move(self, board: Board, idx: int, stone: Cell) -> None:
        """Cập nhật điểm sau khi thu hồi stone tại idx."""
        # Sau undo, ô idx đã trống; tính lại điểm xung quanh
        self._score -= self._score_around(board, idx, stone, before=False)
        self._score += self._score_around(board, idx, stone, before=True)

    @property
    def score(self) -> int:
        return self._score

    def clone_score(self) -> int:
        return self._score

    # ------------------------------------------------------------------
    # Nội bộ
    # ------------------------------------------------------------------

    def _score_around(self, board: Board, idx: int, stone: Cell, before: bool) -> int:
        """
        Tính delta điểm ở 4 đường đi qua idx.
        before=True: tính với board trước khi đặt quân (idx trống).
        before=False: tính với board sau khi đặt quân.
        """
        row, col = idx_to_rc(idx)
        delta = 0
        for dr, dc in DIRECTIONS:
            cells = _extract_line(board, row, col, dr, dc)
            if before:
                # Giả sử ô idx là EMPTY
                local_idx = 0
                r, c = row, col
                while in_bounds(r - dr, c - dc):
                    r -= dr; c -= dc
                local_idx = (row - r) // (dr if dr else 1) if dr else (col - c) // dc
                # Đơn giản hơn: lấy position trong cells
                cells_copy = cells[:]
                pos = self._find_pos(board, row, col, dr, dc)
                if 0 <= pos < len(cells_copy):
                    cells_copy[pos] = Cell.EMPTY
                delta += _score_line(cells_copy, Cell.BLACK) - _score_line(cells_copy, Cell.WHITE)
            else:
                delta += _score_line(cells, Cell.BLACK) - _score_line(cells, Cell.WHITE)
        return delta

    def _find_pos(self, board: Board, row: int, col: int, dr: int, dc: int) -> int:
        """Tìm vị trí của (row, col) trong mảng cells của đường (dr, dc)."""
        r, c = row, col
        pos = 0
        while in_bounds(r - dr, c - dc):
            r -= dr; c -= dc
            pos += 1
        return pos

    def _compute_full(self, board: Board) -> int:
        """Tính điểm toàn bộ (dùng để khởi tạo)."""
        total = 0
        for dr, dc in DIRECTIONS:
            seen: set[int] = set()
            for start_idx in range(BOARD_CELLS):
                sr, sc = idx_to_rc(start_idx)
                # Chỉ xét điểm đầu của đường (không quét ngược)
                pr, pc = sr - dr, sc - dc
                if in_bounds(pr, pc):
                    continue
                cells = _extract_line(board, sr, sc, dr, dc)
                total += _score_line(cells, Cell.BLACK) - _score_line(cells, Cell.WHITE)
        return total
