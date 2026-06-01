"""
core/search.py
Principal Variation Search (PVS / NegaScout) với:
- Killer Move Heuristic: nhớ các nước gây beta-cutoff ở mỗi độ sâu.
- History Heuristic: đếm tần suất cutoff của từng nước đi toàn cục.
- Transposition Table: tránh tính lại vị trí đã duyệt.
- Threat Extension: tìm tiếp khi đến depth 0 mà còn forcing moves.
- Iterative Deepening: đảm bảo luôn có nước tốt trong time limit.

Quy ước điểm (negamax perspective):
  điểm > 0  → lợi cho người đang đi (side_to_move)
  điểm < 0  → bất lợi
"""
from __future__ import annotations

import math
import time
from typing import Optional

from core.types import (
    BOARD_SIZE, BOARD_CELLS, WIN_LENGTH, Cell, DIRECTIONS,
    rc_to_idx, idx_to_rc, in_bounds, SearchConfig,
)
from core.board import Board
from core.candidates import CandidateManager
from core.evaluator import IncrementalEvaluator, score_line_for_stone


# ---------------------------------------------------------------------------
# Transposition Table entry
# ---------------------------------------------------------------------------
_EXACT = 0
_LOWER = 1  # fail-high (score >= beta)
_UPPER = 2  # fail-low  (score <= alpha)

TransEntry = tuple[int, float, int, Optional[int]]  # (depth, score, flag, best_idx)


class SearchTimeout(Exception):
    pass


class PVSSearch:
    """
    Tìm kiếm PVS với Killer & History heuristics và Incremental updates.
    """

    # Điểm thắng/thua tuyệt đối (cao hơn mọi heuristic)
    WIN_SCORE = 10_000_000.0
    MATE_DEPTH_BONUS = 100.0  # Thắng ở depth sâu hơn → điểm thấp hơn một chút

    def __init__(self, config: SearchConfig) -> None:
        self.config = config
        self._tt: dict[int, TransEntry] = {}  # Transposition Table
        self._nodes = 0
        self._deadline: float = 0.0

        # Killer moves: killer[depth][slot] = idx
        max_d = config.depth + config.threat_extension_depth + 2
        self._killers: list[list[Optional[int]]] = [
            [None] * config.killer_slots for _ in range(max_d + 1)
        ]
        # History heuristic: history[side][idx] = cutoff count
        self._history: dict[tuple[int, int], int] = {}

    # ------------------------------------------------------------------
    # Entry point
    # ------------------------------------------------------------------

    def search(
        self,
        board: Board,
        candidates: CandidateManager,
        evaluator: IncrementalEvaluator,
    ) -> tuple[Optional[int], float, int]:
        """
        Iterative deepening PVS.
        Trả về (best_idx, best_score, completed_depth).
        """
        self._nodes = 0
        self._deadline = (
            time.perf_counter() + self.config.time_limit_ms / 1000.0
            if self.config.time_limit_ms
            else math.inf
        )

        # Kiểm tra nước thắng / chặn thắng ngay (depth 0)
        immediate = self._find_immediate(board, candidates)
        if immediate is not None:
            return immediate

        best_idx: Optional[int] = self._first_candidate(candidates)
        best_score = -math.inf
        completed_depth = 0

        for depth in range(1, self.config.depth + 1):
            try:
                idx, score = self._root_search(board, candidates, evaluator, depth)
            except SearchTimeout:
                break
            if idx is not None:
                best_idx = idx
                best_score = score
                completed_depth = depth
                # Đưa best move lên đầu candidates cho lần tiếp
                candidates._candidates.discard(idx)
                candidates._candidates = {idx} | candidates._candidates  # type: ignore

        return best_idx, best_score, completed_depth

    @property
    def nodes_searched(self) -> int:
        return self._nodes

    # ------------------------------------------------------------------
    # Root search (tách riêng để thu best move dễ hơn)
    # ------------------------------------------------------------------

    def _root_search(
        self,
        board: Board,
        candidates: CandidateManager,
        evaluator: IncrementalEvaluator,
        depth: int,
    ) -> tuple[Optional[int], float]:
        self._check_time()
        side = board.side
        best_idx: Optional[int] = None
        best_score = -math.inf
        alpha = -math.inf
        beta = math.inf

        ordered = self._order_moves(board, candidates, depth)
        first = True
        for idx in ordered:
            self._check_time()
            board.make_move(idx, side)
            candidates.on_make_move(board, idx)
            evaluator.on_make_move(board, idx, side)

            if first:
                score = -self._pvs(board, candidates, evaluator, depth - 1, -beta, -alpha, 0)
                first = False
            else:
                # Null window search
                score = -self._pvs(board, candidates, evaluator, depth - 1, -alpha - 1, -alpha, 0)
                if alpha < score < beta:
                    score = -self._pvs(board, candidates, evaluator, depth - 1, -beta, -score, 0)

            evaluator.on_undo_move(board, idx, side)
            candidates.on_undo_move(board, idx)
            board.undo_move(idx, side)

            if score > best_score:
                best_score = score
                best_idx = idx
            alpha = max(alpha, best_score)

        return best_idx, best_score

    # ------------------------------------------------------------------
    # PVS / NegaScout
    # ------------------------------------------------------------------

    def _pvs(
        self,
        board: Board,
        candidates: CandidateManager,
        evaluator: IncrementalEvaluator,
        depth: int,
        alpha: float,
        beta: float,
        ext_depth: int,
    ) -> float:
        self._check_time()
        self._nodes += 1

        # Terminal: thắng/thua
        last = board.last_move
        if last is not None:
            prev_side = Cell.WHITE if board.side == Cell.BLACK else Cell.BLACK
            if board.has_won(last, prev_side):
                return -(self.WIN_SCORE - depth * self.MATE_DEPTH_BONUS)

        if board.is_full():
            return 0.0

        # Transposition Table lookup
        h = board.hash
        cached = self._tt.get(h)
        if cached and cached[0] >= depth:
            cdepth, cscore, cflag, cbest = cached
            if cflag == _EXACT:
                return cscore
            if cflag == _LOWER:
                alpha = max(alpha, cscore)
            elif cflag == _UPPER:
                beta = min(beta, cscore)
            if alpha >= beta:
                return cscore

        # Leaf node
        if depth <= 0:
            if ext_depth < self.config.threat_extension_depth:
                # Threat extension: tìm tiếp nếu có forcing moves
                forcing = self._get_forcing_moves(board, candidates)
                if forcing:
                    ext_cands = CandidateManager(self.config.candidate_radius)
                    ext_cands._candidates = set(forcing)
                    ext_cands._ref_counts = {}
                    return self._pvs(board, ext_cands, evaluator, 0, alpha, beta, ext_depth + 1)
            val = float(evaluator.score if board.side == Cell.WHITE else -evaluator.score)
            self._tt[h] = (0, val, _EXACT, None)
            return val

        ordered = self._order_moves(board, candidates, depth)
        if not ordered:
            val = float(evaluator.score if board.side == Cell.WHITE else -evaluator.score)
            return val

        side = board.side
        orig_alpha = alpha
        best_score = -math.inf
        best_idx: Optional[int] = None
        first = True

        for idx in ordered:
            self._check_time()
            board.make_move(idx, side)
            candidates.on_make_move(board, idx)
            evaluator.on_make_move(board, idx, side)

            if first:
                score = -self._pvs(board, candidates, evaluator, depth - 1, -beta, -alpha, ext_depth)
                first = False
            else:
                score = -self._pvs(board, candidates, evaluator, depth - 1, -alpha - 1, -alpha, ext_depth)
                if alpha < score < beta:
                    score = -self._pvs(board, candidates, evaluator, depth - 1, -beta, -score, ext_depth)

            evaluator.on_undo_move(board, idx, side)
            candidates.on_undo_move(board, idx)
            board.undo_move(idx, side)

            if score > best_score:
                best_score = score
                best_idx = idx
            alpha = max(alpha, best_score)
            if alpha >= beta:
                # Beta cutoff → cập nhật Killer và History
                self._update_killers(idx, depth)
                key = (int(side), idx)
                self._history[key] = self._history.get(key, 0) + (1 << depth)
                break

        # Lưu vào TT
        flag = _EXACT
        if best_score <= orig_alpha:
            flag = _UPPER
        elif best_score >= beta:
            flag = _LOWER
        self._tt[h] = (depth, best_score, flag, best_idx)
        return best_score

    # ------------------------------------------------------------------
    # Move ordering
    # ------------------------------------------------------------------

    def _order_moves(self, board: Board, candidates: CandidateManager, depth: int) -> list[int]:
        """
        Sắp xếp nước đi theo thứ tự ưu tiên:
        1. TT best move
        2. Killer moves
        3. History heuristic
        4. Local shape score (nhanh)
        """
        tt_best: Optional[int] = None
        cached = self._tt.get(board.hash)
        if cached:
            tt_best = cached[3]

        side = int(board.side)
        killers_at = set(k for k in self._killers[depth] if k is not None)

        def priority(idx: int) -> float:
            if idx == tt_best:
                return 1e9
            if idx in killers_at:
                return 5e8
            hist = self._history.get((side, idx), 0)
            return hist + self._quick_score(board, idx)

        raw = candidates.get_candidates(self.config.candidate_limit)
        return sorted(raw, key=priority, reverse=True)

    def _quick_score(self, board: Board, idx: int) -> float:
        """Điểm nhanh dựa trên số quân liền kề (không quét đường đầy đủ)."""
        row, col = idx_to_rc(idx)
        score = 0.0
        side = board.side
        opp = Cell.WHITE if side == Cell.BLACK else Cell.BLACK
        for dr, dc in DIRECTIONS:
            my_count = 0
            op_count = 0
            for sign in (1, -1):
                r, c = row + dr * sign, col + dc * sign
                while in_bounds(r, c):
                    v = board.get(r, c)
                    if v == side:
                        my_count += 1
                    elif v == opp:
                        op_count += 1
                        break
                    else:
                        break
                    r += dr * sign; c += dc * sign
            score += my_count * 100 + op_count * 80
        return score

    # ------------------------------------------------------------------
    # Immediate win / block detection
    # ------------------------------------------------------------------

    def _find_immediate(
        self, board: Board, candidates: CandidateManager
    ) -> Optional[tuple[Optional[int], float, int]]:
        """Kiểm tra nước thắng ngay và nước chặn thắng ngay."""
        side = board.side
        opp = Cell.WHITE if side == Cell.BLACK else Cell.BLACK

        for idx in candidates.get_candidates():
            if board.is_empty_idx(idx):
                board.make_move(idx, side)
                wins = board.has_won(idx, side)
                board.undo_move(idx, side)
                if wins:
                    return (idx, self.WIN_SCORE, 0)

        for idx in candidates.get_candidates():
            if board.is_empty_idx(idx):
                board.make_move(idx, opp)
                wins = board.has_won(idx, opp)
                board.undo_move(idx, opp)
                if wins:
                    return (idx, self.WIN_SCORE * 0.9, 0)

        return None

    def _get_forcing_moves(self, board: Board, candidates: CandidateManager) -> list[int]:
        """Tìm các forcing moves (tạo hoặc chặn open-four / thắng ngay)."""
        side = board.side
        opp = Cell.WHITE if side == Cell.BLACK else Cell.BLACK
        result = []
        for idx in candidates.get_candidates():
            if not board.is_empty_idx(idx):
                continue
            for stone in (side, opp):
                board.make_move(idx, stone)
                if board.has_won(idx, stone):
                    board.undo_move(idx, stone)
                    result.append(idx)
                    break
                # Kiểm tra open-four nhanh
                row, col = idx_to_rc(idx)
                for dr, dc in DIRECTIONS:
                    if score_line_for_stone(board, row, col, dr, dc, stone) >= 100_000:
                        result.append(idx)
                        break
                board.undo_move(idx, stone)
        return list(set(result))

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _update_killers(self, idx: int, depth: int) -> None:
        """Thêm idx vào killer list tại depth (FIFO, bỏ duplicate)."""
        if depth >= len(self._killers):
            return
        slots = self._killers[depth]
        if idx not in slots:
            slots.pop()
            slots.insert(0, idx)

    def _first_candidate(self, candidates: CandidateManager) -> Optional[int]:
        raw = candidates.get_candidates()
        return raw[0] if raw else None

    def _check_time(self) -> None:
        if time.perf_counter() >= self._deadline:
            raise SearchTimeout
