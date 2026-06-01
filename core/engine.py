"""
core/engine.py
Public API cho Gomoku AI – lớp duy nhất mà frontend cần import.

Cung cấp:
- GomokuEngine: wrapper gọi PVSSearch, Board, CandidateManager, IncrementalEvaluator.
- get_best_move(board_2d, stone) → (row, col) | None
- evaluate(board_2d) → int
- get_analysis(board_2d, stone) → MoveAnalysis
"""
from __future__ import annotations

from typing import Optional

from core.types import BOARD_SIZE, BOARD_CELLS, Cell, SearchConfig, MoveAnalysis, rc_to_idx, idx_to_rc
from core.board import Board
from core.candidates import CandidateManager
from core.evaluator import IncrementalEvaluator
from core.search import PVSSearch


# Cấu hình mặc định cho từng mức độ khó
DIFFICULTY_CONFIGS: dict[str, SearchConfig] = {
    "easy": SearchConfig(
        depth=2,
        time_limit_ms=400,
        candidate_radius=2,
        candidate_limit=8,
        use_pvs=True,
        killer_slots=2,
        threat_extension_depth=0,
    ),
    "medium": SearchConfig(
        depth=3,
        time_limit_ms=1200,
        candidate_radius=2,
        candidate_limit=12,
        use_pvs=True,
        killer_slots=2,
        threat_extension_depth=1,
    ),
    "hard": SearchConfig(
        depth=4,
        time_limit_ms=2500,
        candidate_radius=3,
        candidate_limit=16,
        use_pvs=True,
        killer_slots=2,
        threat_extension_depth=1,
    ),
}


class GomokuEngine:
    """
    Entry point duy nhất cho frontend.

    Cách dùng::

        engine = GomokuEngine(difficulty="medium")
        analysis = engine.get_analysis(board_2d, stone=1)
        row, col = analysis.move
    """

    def __init__(self, difficulty: str = "medium", config: Optional[SearchConfig] = None) -> None:
        if config is not None:
            self.config = config
        else:
            if difficulty not in DIFFICULTY_CONFIGS:
                raise ValueError(f"difficulty phải là một trong: {list(DIFFICULTY_CONFIGS)}")
            self.config = DIFFICULTY_CONFIGS[difficulty]

        self.difficulty = difficulty
        self._search = PVSSearch(self.config)

    # ------------------------------------------------------------------
    # API chính
    # ------------------------------------------------------------------

    def get_best_move(
        self,
        board_2d: list[list[int]],
        stone: int = Cell.BLACK,
    ) -> Optional[tuple[int, int]]:
        """
        Tìm nước đi tốt nhất.

        Parameters
        ----------
        board_2d : list[list[int]]
            Ma trận 15×15; 0=trống, 1=BLACK(AI), -1=WHITE(human).
        stone : int
            Bên đang đến lượt (Cell.BLACK=1 hoặc Cell.WHITE=-1).

        Returns
        -------
        (row, col) hoặc None nếu không còn nước đi hợp lệ.
        """
        analysis = self.get_analysis(board_2d, stone)
        return analysis.move

    def get_analysis(
        self,
        board_2d: list[list[int]],
        stone: int = Cell.BLACK,
    ) -> MoveAnalysis:
        """
        Tìm nước đi và trả về đầy đủ thông tin phân tích.
        """
        import time
        t_start = time.perf_counter()

        board = Board.from_2d(board_2d)
        # Override side nếu khác mặc định (board.from_2d luôn để BLACK đi trước)
        board._side = Cell(stone)  # type: ignore[attr-defined]

        candidates = CandidateManager(self.config.candidate_radius)
        candidates.bootstrap(board)

        # Board trống → đánh trung tâm ngay
        if board.stone_count == 0:
            center = BOARD_SIZE // 2
            elapsed = (time.perf_counter() - t_start) * 1000
            return MoveAnalysis(
                move=(center, center),
                score=0.0,
                reason="opening_center",
                completed_depth=0,
                nodes_searched=0,
                elapsed_ms=elapsed,
            )

        evaluator = IncrementalEvaluator()
        evaluator.full_eval(board)

        best_idx, best_score, completed_depth = self._search.search(board, candidates, evaluator)

        elapsed = (time.perf_counter() - t_start) * 1000
        move = idx_to_rc(best_idx) if best_idx is not None else None
        reason = self._classify_reason(board_2d, move, stone)

        return MoveAnalysis(
            move=move,
            score=float(best_score),
            reason=reason,
            completed_depth=completed_depth,
            nodes_searched=self._search.nodes_searched,
            elapsed_ms=elapsed,
        )

    def evaluate(self, board_2d: list[list[int]]) -> int:
        """Đánh giá tĩnh bàn cờ (điểm BLACK - điểm WHITE)."""
        board = Board.from_2d(board_2d)
        ev = IncrementalEvaluator()
        return ev.full_eval(board)

    # ------------------------------------------------------------------
    # Phân loại lý do nước đi (để frontend hiển thị)
    # ------------------------------------------------------------------

    def _classify_reason(
        self,
        board_2d: list[list[int]],
        move: Optional[tuple[int, int]],
        stone: int,
    ) -> str:
        if move is None:
            return "no_legal_move"

        row, col = move
        board = Board.from_2d(board_2d)
        idx = rc_to_idx(row, col)
        opp = Cell.WHITE if stone == Cell.BLACK else Cell.BLACK

        # Kiểm tra thắng ngay
        board.make_move(idx, Cell(stone))
        if board.has_won(idx, Cell(stone)):
            board.undo_move(idx, Cell(stone))
            return "winning_move"
        board.undo_move(idx, Cell(stone))

        # Kiểm tra chặn thắng ngay
        board.make_move(idx, opp)
        if board.has_won(idx, opp):
            board.undo_move(idx, opp)
            return "blocking_win"
        board.undo_move(idx, opp)

        return "best_search_score"
