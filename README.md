# Gomoku AI - Cờ Caro Đa Nền Tảng (Minimax & PVS)

Dự án phát triển một AI chơi game Gomoku (Cờ Caro 15x15) hiệu suất cao bằng Python. Hệ thống được tối ưu hóa sâu ở lõi thuật toán (Core Engine) bằng các kỹ thuật tiên tiến và hỗ trợ hai giao diện độc lập: Giao diện Web (FastAPI) và Giao diện Desktop (PyQt6).

## 🌟 Tính Năng Nổi Bật

### 1. Lõi AI Tối Ưu (Core Engine)
- **Cấu trúc dữ liệu 1D:** Biểu diễn bàn cờ bằng mảng 1 chiều (1D array) giúp tăng tốc độ truy xuất bộ nhớ và tối ưu cache so với mảng 2D truyền thống.
- **Tính toán Tiệm tiến (Incremental Updates):**
  - **Zobrist Hashing:** Cập nhật mã băm trạng thái bàn cờ qua phép XOR chỉ với nước đi mới, bỏ qua việc tính lại từ đầu.
  - **Evaluation (Đánh giá):** Tính toán điểm số bàn cờ bằng cách chỉ đánh giá sự thay đổi ở hàng, cột và 2 đường chéo liên quan đến nước đi vừa đánh.
  - **Candidate Generation:** Mở rộng tiệm tiến các ô lân cận thay vì quét toàn bộ bàn cờ 15x15 mỗi lần sinh nước đi.
- **Thuật toán Tìm kiếm & Cắt tỉa:**
  - Minimax kết hợp Alpha-Beta Pruning.
  - **PVS (Principal Variation Search):** Tối ưu hóa cửa sổ tìm kiếm (Null Window Search) để cắt tỉa nhánh nhanh hơn.
- **Heuristics:**
  - **Killer Move Heuristic:** Ưu tiên duyệt các nước đi gây ra cắt tỉa (Beta-cutoff) ở các nhánh trước đó.
  - **History Heuristic:** Đánh giá điểm lịch sử của các nước đi thành công để sắp xếp thứ tự duyệt (Move Ordering).

### 2. Giao diện (Frontends)
- **Giao diện Desktop (PyQt6):** Chạy mượt mà, không bị "đơ" (Not Responding) khi AI suy nghĩ nhờ sử dụng đa luồng (`QThread`).
- **Giao diện Web (FastAPI + HTML/JS):** Dễ dàng triển khai thành service, tương tác thông qua REST API.

### 3. Theo dõi & Thống kê
- **Stats Tracker:** Tự động ghi log độ sâu (depth) mà AI đạt được sau mỗi lượt đi vào file JSON và tính toán độ sâu trung bình cục bộ/toàn cục.

---

## 📂 Cấu Trúc Thư Mục

```text
gomoku_ai/
├── core/
│   ├── __init__.py
│   ├── types.py          # Hằng số, Dataclasses
│   ├── board.py          # Quản lý bàn cờ 1D + Incremental Zobrist
│   ├── evaluator.py      # Heuristic Evaluation tiệm tiến
│   ├── candidates.py     # Sinh nước đi (Move Generation) tiệm tiến
│   ├── search.py         # Thuật toán PVS, Killer/History Heuristics
│   └── engine.py         # Lớp GomokuEngine (API giao tiếp chính)
├── frontend_web/
│   ├── __init__.py
│   ├── server.py         # Web Server sử dụng FastAPI
│   └── static/
│       └── index.html    # Giao diện Web (HTML/CSS/JS)
├── frontend_pyqt/
│   ├── __init__.py
│   └── app.py            # Giao diện Desktop sử dụng PyQt6
├── stats_tracker.py      # Module lưu và phân tích lịch sử độ sâu
├── requirements.txt      # Danh sách thư viện Python cần thiết
└── README.md             # Tài liệu dự án
```
## ⚙️ Cài Đặt
**Yêu cầu hệ thống**: Python 3.8 trở lên.

Clone hoặc tải dự án về máy.  
Khuyến nghị tạo môi trường ảo (Virtual Environment):

```Bash
python -m venv venv
source venv/bin/activate  # Trên Linux/Mac
venv\Scripts\activate     # Trên Windows
```
**Cài đặt các thư viện cần thiết:**
```Bash
pip install -r requirements.txt
```
🚀 Hướng Dẫn Sử Dụng
Bạn có thể chạy dự án thông qua một trong hai giao diện sau (đảm bảo bạn đang đứng ở thư mục gốc gomoku_ai/ trên terminal):

Cách 1: Chạy giao diện Desktop (PyQt6)
Giao diện này cho phép bạn chơi trực tiếp trên máy tính.

```Bash
python frontend_pyqt/app.py
```
Cách 2: Chạy giao diện Web (FastAPI)
Giao diện này khởi tạo một local server, bạn sẽ chơi thông qua trình duyệt web.

Khởi động Server:

```Bash
uvicorn frontend_web.server:app --reload
```
Lưu ý: Nếu bạn chạy file server.py trực tiếp bằng python frontend_web/server.py, server cũng sẽ tự động khởi chạy tại cổng mặc định.

Truy cập: Mở trình duyệt và truy cập vào địa chỉ:

Plaintext
[http://127.0.0.1:8000](http://127.0.0.1:8000)  
📝 Theo Dõi Lịch Sử
Mỗi khi AI thực hiện một nước đi, độ sâu tìm kiếm thực tế sẽ được ghi lại vào file depth_history.json tại thư mục gốc. Bạn có thể mở file này để kiểm tra, hoặc xem thông báo "Độ sâu trung bình" in ra trực tiếp trên Console/Giao diện sau mỗi lượt.