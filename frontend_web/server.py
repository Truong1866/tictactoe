"""
frontend_web/server.py
Web server FastAPI cho Gomoku AI.

Chạy:
    cd gomoku_ai
    uvicorn frontend_web.server:app --reload --port 8000

Sau đó mở http://127.0.0.1:8000 trên trình duyệt.
"""
from __future__ import annotations

import sys
from pathlib import Path

# Đảm bảo thư mục gốc dự án có trong sys.path
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, field_validator

from core.engine import GomokuEngine, DIFFICULTY_CONFIGS
from core.types import Cell, BOARD_SIZE
from stats_tracker import get_tracker


app = FastAPI(title="Gomoku AI – Web Frontend", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve static files (HTML/CSS/JS)
STATIC_DIR = Path(__file__).resolve().parent / "static"
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

# Cache engine theo difficulty
_engines: dict[str, GomokuEngine] = {}


def _get_engine(difficulty: str) -> GomokuEngine:
    if difficulty not in _engines:
        _engines[difficulty] = GomokuEngine(difficulty=difficulty)
    return _engines[difficulty]


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------

class MoveRequest(BaseModel):
    board: list[list[int]] = Field(..., description="Ma trận 15×15")
    stone: int = Field(default=1, description="Bên đang đến lượt: 1=BLACK(AI), -1=WHITE")
    difficulty: str = Field(default="medium")

    @field_validator("board")
    @classmethod
    def validate_board(cls, v: list[list[int]]) -> list[list[int]]:
        if len(v) != BOARD_SIZE:
            raise ValueError(f"Board phải có {BOARD_SIZE} hàng.")
        for row in v:
            if len(row) != BOARD_SIZE:
                raise ValueError(f"Mỗi hàng phải có {BOARD_SIZE} cột.")
            for cell in row:
                if cell not in {0, 1, -1}:
                    raise ValueError("Giá trị ô phải là 0, 1 hoặc -1.")
        return v

    @field_validator("stone")
    @classmethod
    def validate_stone(cls, v: int) -> int:
        if v not in {1, -1}:
            raise ValueError("stone phải là 1 hoặc -1.")
        return v

    @field_validator("difficulty")
    @classmethod
    def validate_difficulty(cls, v: str) -> str:
        v = v.lower().strip()
        if v not in DIFFICULTY_CONFIGS:
            raise ValueError(f"difficulty phải là: {list(DIFFICULTY_CONFIGS.keys())}")
        return v


class MoveResponse(BaseModel):
    row: int | None
    col: int | None
    score: float
    reason: str
    completed_depth: int
    nodes_searched: int
    elapsed_ms: float
    average_depth: float
    message: str


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.get("/")
def index() -> FileResponse:
    """Serve trang chủ HTML."""
    return FileResponse(str(STATIC_DIR / "index.html"))


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok", "version": "2.0.0"}


@app.post("/api/get-move", response_model=MoveResponse)
def get_move(payload: MoveRequest) -> MoveResponse:
    """Tính nước đi tốt nhất và trả về kết quả phân tích."""
    engine = _get_engine(payload.difficulty)
    tracker = get_tracker()

    try:
        analysis = engine.get_analysis(payload.board, stone=payload.stone)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    # Ghi log
    tracker.record_search(
        completed_depth=analysis.completed_depth,
        nodes_searched=analysis.nodes_searched,
        elapsed_ms=analysis.elapsed_ms,
        move=analysis.move,
        reason=analysis.reason,
    )

    return MoveResponse(
        row=analysis.move[0] if analysis.move else None,
        col=analysis.move[1] if analysis.move else None,
        score=analysis.score,
        reason=analysis.reason,
        completed_depth=analysis.completed_depth,
        nodes_searched=analysis.nodes_searched,
        elapsed_ms=analysis.elapsed_ms,
        average_depth=tracker.average_depth(),
        message="Move generated successfully." if analysis.move else "Game over.",
    )


@app.get("/api/stats")
def get_stats() -> dict:
    """Trả về thống kê độ sâu tích lũy."""
    tracker = get_tracker()
    return {
        "total_records": tracker.total_records(),
        "average_depth": tracker.average_depth(),
        "session_average_depth": tracker.session_average_depth(),
    }
