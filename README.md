# CampusGuide AI

Chatbot hỏi đáp quy chế và thông tin đào tạo bằng RAG. Toàn bộ viết bằng **Python** (FastAPI + SQLite), giao diện HTML/CSS/JS phục vụ ngay từ FastAPI, nên chỉ cần chạy **một server**.

Phần cần bạn tự kiểm tra (khóa API, model, OCR, quy chế thật...) nằm trong **[HUONG_DAN_KIEM_TRA.md](HUONG_DAN_KIEM_TRA.md)**.

## Chạy trong PyCharm

1. `File > Open` thư mục dự án. PyCharm sẽ hỏi tạo interpreter: chọn **Virtualenv** (Python 3.10 trở lên).
2. Mở **Terminal** của PyCharm, gõ: `pip install -r requirements.txt`
3. Chuột phải file **`run.py`** > **Run 'run'**.
4. Mở trình duyệt: <http://localhost:8000>

Sửa code trong thư mục `app/` rồi lưu thì server tự khởi động lại. Dừng server bằng nút Stop đỏ của PyCharm.

Cấu hình nằm trong file `.env`: sao chép `.env.example` thành `.env` rồi sửa (khởi động lại server sau khi sửa).

## Tài khoản

- Lần chạy đầu hệ thống tạo quản trị viên từ `.env` (`ADMIN_USERNAME`, mặc định `admin`; `ADMIN_PASSWORD`). Nếu để trống mật khẩu, hệ thống tự sinh và **in ra cửa sổ Run của PyCharm một lần**.
- Ai cũng tự đăng ký được ở trang Đăng nhập, tài khoản mới chỉ có Hỏi đáp AI và Thư viện văn bản.
- Quản trị viên vào **Quản lý tài khoản** để bật quyền **Quản trị dữ liệu** cho từng người dùng. Chỉ quản trị viên thấy mục này.
- Quên mật khẩu quản trị viên cuối cùng: đặt `ADMIN_FORCE_RESET=1` và `ADMIN_PASSWORD=mật_khẩu_mới` trong `.env`, chạy lại một lần rồi xóa dòng `ADMIN_FORCE_RESET`.
- Cơ sở dữ liệu cũ (lịch sử gắn theo trình duyệt) được tự bỏ phần hội thoại khi nâng cấp; văn bản đã tải lên vẫn giữ.

## Dùng thử trong 3 phút

1. Đăng nhập bằng tài khoản quản trị viên, vào **Quản trị dữ liệu**, tải `samples/quy_che_mau_thu_nghiem.txt` (văn bản **tự soạn để thử**, không phải quy chế thật), chọn loại "Quy chế đào tạo".
2. Chờ trạng thái chuyển sang **Đã lập chỉ mục**.
3. Vào **Hỏi đáp AI**, bấm một gợi ý câu hỏi.

Khi chưa cấu hình LLM, hệ thống vẫn tìm đúng các Điều liên quan và liệt kê ở panel nguồn, nhưng **chưa soạn câu trả lời**. Giao diện báo rõ điều này.

## Cấu hình (file `.env`)

| Tính năng | Biến | Cần cài thêm |
|---|---|---|
| Câu trả lời của LLM | `LLM_PROVIDER` = `gemini` / `anthropic` / `openai` (kèm khóa API) | Không |
| Cho máy khác trong LAN vào | `APP_HOST=0.0.0.0` (mặc định chỉ máy bạn vào được) | Không |
| Quản trị viên đầu tiên | `ADMIN_USERNAME`, `ADMIN_PASSWORD` (xem mục Tài khoản) | Không |
| Embedding ngữ nghĩa | `EMBEDDING_MODEL` (ví dụ `BAAI/bge-m3`) | `sentence-transformers` |
| Rerank | `RERANK_MODEL` (ví dụ `BAAI/bge-reranker-v2-m3`) | `sentence-transformers` |
| Kho vector Chroma | `VECTOR_STORE=chroma` | `chromadb` + bật embedding |
| OCR PDF scan | `OCR=1`, `OCR_LANG=vie+eng`, `TESSERACT_CMD` | `pypdfium2 pytesseract pillow` + chương trình Tesseract |
| Ngưỡng lọc | `MIN_COVERAGE`, `REL_SCORE`, `TOP_K` | Không |

Mọi thứ tùy chọn đều **tắt mặc định**, nên chạy được ngay chỉ với `requirements.txt`. Thư viện tùy chọn nằm trong `requirements-optional.txt`.

## Cấu trúc

```
run.py               chạy server (bấm Run trong PyCharm)
app/
  main.py            API + các trang
  db.py, config.py   SQLite, cấu hình từ .env
  rag/
    extract.py       đọc PDF/DOCX/TXT, OCR, cảnh báo khi chữ bị vỡ dấu
    chunking.py      chia đoạn theo Chương/Điều/Khoản      <- điểm nhấn kỹ thuật
    retrieval.py     BM25 (+ embedding, RRF), ưu tiên bản mới/còn hiệu lực, lọc độ phủ, kéo Điều được dẫn tới
    rerank.py        cross-encoder tùy chọn
    vectorstore.py   Chroma tùy chọn
    embedding.py     sentence-transformers tùy chọn
    pipeline.py      viết lại câu hỏi nối tiếp, prompt, từ chối khi thiếu căn cứ
    llm.py           Gemini / Anthropic / OpenAI-compatible
    ingest.py        trích xuất > chia đoạn > lập chỉ mục (chạy nền)
  templates/, static/  giao diện
data/                CSDL SQLite, file đã tải lên, Chroma (tự tạo)
samples/             tài liệu thử nghiệm
```

## Đã làm được

- Hỏi đáp có trích dẫn [1], [2]; bấm số để xem đúng đoạn, Điều, trang, số hiệu, hiệu lực; từ khóa khớp được tô sáng; mở văn bản gốc (PDF mở đúng trang).
- Từ chối khi không có căn cứ (ngưỡng độ phủ từ khóa + chỉ dẫn trong prompt), không gắn nguồn cũ vào câu trả lời mới.
- Hỏi nối tiếp (viết lại câu hỏi bằng LLM, nếu chưa có LLM thì ghép với câu hỏi trước).
- Tự kéo thêm Điều được dẫn tới ("theo Điều 2 của quy chế này").
- Ưu tiên văn bản còn hiệu lực và mới nhất trong cùng loại; cảnh báo khi có nhiều phiên bản hoặc nguồn hết hiệu lực/đã thay thế.
- Lịch sử hội thoại theo từng trình duyệt (đổi tên, xóa), phản hồi hữu ích/chưa hữu ích, sao chép câu trả lời.
- Thư viện văn bản: tìm theo tên/số hiệu/nội dung, lọc theo loại/năm/hiệu lực, sắp xếp theo cột, xem chi tiết theo Điều (kèm văn bản thay thế).
- Quản trị: chọn file là tự điền sẵn tên, loại, số hiệu, cơ quan, ngày ban hành / hiệu lực, văn bản bị thay thế (đọc từ nội dung, tô nền để bạn kiểm tra; thử với `samples/quy_che_hoc_bong_mau.txt`); tải lên có kiểm tra và tiến trình thật, trạng thái xử lý theo từng bước, sửa metadata, thay file, thử lại, xóa có xác nhận.
- Tài khoản: đăng ký / đăng nhập, mật khẩu băm PBKDF2 có salt, mỗi tài khoản có lịch sử hỏi đáp riêng; quản trị viên thêm / sửa / khóa / xóa / tìm tài khoản và cấp quyền Quản trị dữ liệu.
- Giao diện theo bản thiết kế (menu trên đầu trang, nền giấy ấm, 4 bước tra cứu khi chờ, panel nguồn trích dẫn, trang chi tiết văn bản /library/{id}).
- Tùy chọn: embedding, rerank, Chroma, OCR.

## Giới hạn hiện tại (nói thẳng)

- **Chưa có trang Đánh giá AI** và script đo Recall@k, theo quyết định làm sau.
- **Hiệu lực văn bản do quản trị viên nhập**, hệ thống không tự suy ra văn bản nào còn hiệu lực. Nó chỉ ưu tiên và cảnh báo dựa trên giá trị đã nhập.
- Số trang của một Điều là trang nơi Điều bắt đầu. DOCX/TXT không có số trang.
- Một số PDF cũ bị lỗi font làm vỡ dấu tiếng Việt. Hệ thống hiện cảnh báo chất lượng ở trang quản trị, khi đó hãy xuất lại PDF từ Word hoặc dùng DOCX. OCR có thể sai chữ và số.
- Tài khoản chưa có quên mật khẩu qua email (quản trị viên đặt lại mật khẩu giúp) và chưa có xác thực hai lớp. Khi đưa lên Internet cần chạy sau HTTPS và đặt `COOKIE_SECURE=1`.
- Chưa dùng Qdrant (chỉ có SQLite và Chroma).
- Các ngưỡng `MIN_COVERAGE` và `REL_SCORE` được chỉnh theo tài liệu mẫu nhỏ, cần chỉnh lại với quy chế thật (Bước 8 trong `HUONG_DAN_KIEM_TRA.md`).
- **Chưa kiểm chứng:** chạy trên Windows/PyCharm, LLM thật, embedding/rerank với model thật, OCR tiếng Việt. Hướng dẫn thử nằm trong `HUONG_DAN_KIEM_TRA.md`.
