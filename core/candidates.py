"""
core/candidates.py
Sinh danh sách nước đi tiềm năng (candidate moves) tiệm tiến.

Ý tưởng:
- Duy trì một set các ô trống nằm trong bán kính R quanh các quân đã đánh.
- Khi make_move(idx): thêm các hàng xóm của idx vào set (nếu còn trống).
- Khi undo_move(idx): kiểm tra lại và xóa các ô không còn là hàng xóm hợp lệ.
- Luôn giữ tactical candidates (nước thắng / chặn thắng) bất kể limit.
"""
from __future__ import annotations

from typing import Iterable

from core.types import (
    BOARD_SIZE, BOARD_CELLS, Cell,
    rc_to_idx, idx_to_rc, in_bounds,
)
from core.board import Board


class CandidateManager:
    """
    Quản lý tập hợp nước đi tiềm năng theo cách tiệm tiến.

    Mỗi node trong cây tìm kiếm nhận được snapshot của CandidateManager
    cha và cập nhật thêm sau khi make_move.
    """

    __slots__ = ("_candidates", "_radius", "_ref_counts")

    def __init__(self, radius: int = 2) -> None:
        self._radius = radius
        # _candidates: set các idx ô trống là ứng viên
        self._candidates: set[int] = set()
        # _ref_counts[idx] = số quân đã đánh trong bán kính radius quanh idx
        # Dùng để biết khi nào xóa ô ra khỏi candidates khi undo
        self._ref_counts: dict[int, int] = {}

    def bootstrap(self, board: Board) -> None:
        """Khởi tạo candidates từ board đã có sẵn quân (node gốc)."""
        self._candidates.clear()
        self._ref_counts.clear()
        for idx in range(BOARD_CELLS):
            if board.get_idx(idx) != Cell.EMPTY:
                self._expand(board, idx)

    def _expand(self, board: Board, center_idx: int) -> None:
        """Thêm các ô trống xung quanh center_idx vào candidates."""
        cr, cc = idx_to_rc(center_idx)
        for dr in range(-self._radius, self._radius + 1):
            for dc in range(-self._radius, self._radius + 1):
                if dr == 0 and dc == 0:
                    continue
                nr, nc = cr + dr, cc + dc
                if not in_bounds(nr, nc):
                    continue
                nidx = rc_to_idx(nr, nc)
                if board.get_idx(nidx) == Cell.EMPTY:
                    self._candidates.add(nidx)
                    self._ref_counts[nidx] = self._ref_counts.get(nidx, 0) + 1

    def _shrink(self, board: Board, center_idx: int) -> None:
        """Xóa các ô hàng xóm khỏi candidates nếu không còn quân nào gần đó."""
        cr, cc = idx_to_rc(center_idx)
        for dr in range(-self._radius, self._radius + 1):
            for dc in range(-self._radius, self._radius + 1):
                if dr == 0 and dc == 0:
                    continue
                nr, nc = cr + dr, cc + dc
                if not in_bounds(nr, nc):
                    continue
                nidx = rc_to_idx(nr, nc)
                if nidx in self._ref_counts:
                    self._ref_counts[nidx] -= 1
                    if self._ref_counts[nidx] <= 0:
                        self._ref_counts.pop(nidx, None)
                        self._candidates.discard(nidx)

    def on_make_move(self, board: Board, idx: int) -> None:
        """
        Gọi SAU KHI board.make_move(idx) đã chạy.
        - Xóa idx khỏi candidates (ô không còn trống).
        - Thêm hàng xóm mới của idx.
        """
        self._candidates.discard(idx)
        self._ref_counts.pop(idx, None)
        self._expand(board, idx)

    def on_undo_move(self, board: Board, idx: int) -> None:
        """
        Gọi SAU KHI board.undo_move(idx) đã chạy.
        - Thêm lại idx vào candidates nếu nó có hàng xóm.
        - Shrink các hàng xóm không còn được tham chiếu.
        """
        self._shrink(board, idx)
        # Nếu idx có quân liền kề, thêm lại vào candidates
        cr, cc = idx_to_rc(idx)
        for dr in range(-self._radius, self._radius + 1):
            for dc in range(-self._radius, self._radius + 1):
                if dr == 0 and dc == 0:
                    continue
                nr, nc = cr + dr, cc + dc
                if not in_bounds(nr, nc):
                    continue
                nidx = rc_to_idx(nr, nc)
                if board.get_idx(nidx) != Cell.EMPTY:
                    self._candidates.add(idx)
                    self._ref_counts[idx] = self._ref_counts.get(idx, 0) + 1
                    break

    def get_candidates(self, limit: int = 0) -> list[int]:
        """Trả về danh sách candidates. limit=0 nghĩa là không giới hạn."""
        result = list(self._candidates)
        if limit > 0 and len(result) > limit:
            return result[:limit]
        return result

    def clone(self) -> "CandidateManager":
        """Sao chép để truyền xuống node con trong cây tìm kiếm."""
        c = CandidateManager(self._radius)
        c._candidates = self._candidates.copy()
        c._ref_counts = self._ref_counts.copy()
        return c

    def __len__(self) -> int:
        return len(self._candidates)
