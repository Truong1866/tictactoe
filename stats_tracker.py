"""
stats_tracker.py
Module ghi log và thống kê độ sâu tìm kiếm của AI.

Chức năng:
- record_search(): lưu thông tin sau mỗi lượt tính toán vào file JSON.
- average_depth(): đọc lịch sử và tính độ sâu trung bình.
- print_stats(): in thống kê ra console sau mỗi lượt.

File lịch sử mặc định: depth_history.json (cùng thư mục dự án).
"""
from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Optional


DEFAULT_HISTORY_FILE = Path(__file__).resolve().parent / "depth_history.json"


@dataclass
class SearchRecord:
    """Một bản ghi cho một lượt tìm kiếm."""
    timestamp: float          # Unix timestamp
    completed_depth: int      # Độ sâu thực tế đã hoàn thành
    nodes_searched: int       # Số node đã duyệt
    elapsed_ms: float         # Thời gian tính toán (ms)
    move_row: Optional[int]   # Nước đi chọn
    move_col: Optional[int]
    reason: str               # Lý do chọn nước


class StatsTracker:
    """
    Ghi log và thống kê mỗi lượt AI tính toán.

    Parameters
    ----------
    filepath : Path | str
        Đường dẫn file JSON lưu lịch sử. Mặc định: depth_history.json.
    verbose : bool
        Nếu True, in thống kê ra console sau mỗi lần record.
    """

    def __init__(
        self,
        filepath: Path | str = DEFAULT_HISTORY_FILE,
        verbose: bool = True,
    ) -> None:
        self.filepath = Path(filepath)
        self.verbose = verbose
        self._session_records: list[SearchRecord] = []

    # ------------------------------------------------------------------
    # Ghi log
    # ------------------------------------------------------------------

    def record_search(
        self,
        completed_depth: int,
        nodes_searched: int = 0,
        elapsed_ms: float = 0.0,
        move: Optional[tuple[int, int]] = None,
        reason: str = "unknown",
    ) -> None:
        """
        Lưu thông tin một lượt tìm kiếm vào file và session hiện tại.

        Parameters
        ----------
        completed_depth : int
            Độ sâu thực tế đã hoàn thành (từ MoveAnalysis.completed_depth).
        nodes_searched : int
            Số node đã duyệt trong lượt này.
        elapsed_ms : float
            Thời gian tính toán tính bằng millisecond.
        move : (row, col) | None
            Nước đi AI chọn.
        reason : str
            Lý do chọn nước (winning_move, blocking_win, ...).
        """
        record = SearchRecord(
            timestamp=time.time(),
            completed_depth=completed_depth,
            nodes_searched=nodes_searched,
            elapsed_ms=elapsed_ms,
            move_row=move[0] if move else None,
            move_col=move[1] if move else None,
            reason=reason,
        )
        self._session_records.append(record)
        self._append_to_file(record)

        if self.verbose:
            self.print_stats(record)

    def _append_to_file(self, record: SearchRecord) -> None:
        """Đọc file hiện tại (nếu có), thêm record mới, ghi lại."""
        history = self._load_all()
        history.append(asdict(record))
        try:
            self.filepath.write_text(
                json.dumps(history, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except OSError as exc:
            print(f"[StatsTracker] Không thể ghi file: {exc}")

    # ------------------------------------------------------------------
    # Đọc & thống kê
    # ------------------------------------------------------------------

    def _load_all(self) -> list[dict]:
        """Đọc toàn bộ lịch sử từ file. Trả về list rỗng nếu chưa có."""
        if not self.filepath.exists():
            return []
        try:
            data = json.loads(self.filepath.read_text(encoding="utf-8"))
            return data if isinstance(data, list) else []
        except (json.JSONDecodeError, OSError):
            return []

    def average_depth(self) -> float:
        """
        Tính độ sâu trung bình của tất cả các lượt đã lưu trong file.

        Returns
        -------
        float
            Độ sâu trung bình. 0.0 nếu chưa có dữ liệu.
        """
        history = self._load_all()
        if not history:
            return 0.0
        depths = [r.get("completed_depth", 0) for r in history if isinstance(r, dict)]
        return sum(depths) / len(depths) if depths else 0.0

    def session_average_depth(self) -> float:
        """Độ sâu trung bình chỉ trong phiên hiện tại (chưa lưu file)."""
        if not self._session_records:
            return 0.0
        return sum(r.completed_depth for r in self._session_records) / len(self._session_records)

    def total_records(self) -> int:
        """Tổng số lượt đã ghi trong file."""
        return len(self._load_all())

    def clear_history(self) -> None:
        """Xóa toàn bộ lịch sử (file + session)."""
        self._session_records.clear()
        if self.filepath.exists():
            self.filepath.write_text("[]", encoding="utf-8")

    # ------------------------------------------------------------------
    # In thống kê
    # ------------------------------------------------------------------

    def print_stats(self, latest: Optional[SearchRecord] = None) -> None:
        """
        In thống kê ra console.

        Parameters
        ----------
        latest : SearchRecord | None
            Bản ghi vừa thêm (in thêm chi tiết lượt này).
        """
        avg = self.average_depth()
        total = self.total_records()
        session_avg = self.session_average_depth()

        print("─" * 48)
        if latest:
            move_str = (
                f"({latest.move_row}, {latest.move_col})"
                if latest.move_row is not None
                else "None"
            )
            print(f"  [AI] Nước đi  : {move_str}  ({latest.reason})")
            print(f"  [AI] Độ sâu   : {latest.completed_depth}  |  Nodes: {latest.nodes_searched:,}")
            print(f"  [AI] Thời gian: {latest.elapsed_ms:.1f} ms")
        print(f"  [Stats] Tổng lượt         : {total}")
        print(f"  [Stats] Độ sâu TB (file)  : {avg:.2f}")
        print(f"  [Stats] Độ sâu TB (phiên) : {session_avg:.2f}")
        print("─" * 48)


# ---------------------------------------------------------------------------
# Convenience singleton – các module khác import trực tiếp
# ---------------------------------------------------------------------------
_default_tracker: Optional[StatsTracker] = None


def get_tracker(filepath: Path | str = DEFAULT_HISTORY_FILE, verbose: bool = True) -> StatsTracker:
    """Trả về tracker singleton mặc định (tạo mới nếu chưa có)."""
    global _default_tracker
    if _default_tracker is None:
        _default_tracker = StatsTracker(filepath=filepath, verbose=verbose)
    return _default_tracker
