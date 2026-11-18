# Hướng dẫn kiểm tra từng bước

Tài liệu này dành cho những phần **mình chưa thể tự thử** vì cần máy Windows, khóa API hoặc model tải về của bạn. Code của các phần này đã viết xong; việc của bạn là bật lên, thử, và báo lại kết quả.

## Bảng tổng quan: ai đã kiểm tra gì

| Phần | Trạng thái | Ghi chú |
|---|---|---|
| Tải lên, chia đoạn Điều/Khoản, BM25, từ chối, nguồn, tô sáng từ khóa | Đã thử | Trên Linux, tài liệu mẫu và PDF/DOCX/TXT |
| Ưu tiên văn bản còn hiệu lực/mới nhất, thay file, sắp xếp, sidebar thu gọn | Đã thử | Trình duyệt Chromium, desktop, tablet, điện thoại |
| Chroma (lưu/tìm/xóa vector) | Đã thử | Với embedding **giả**, chưa với model thật |
| Rerank | Đã thử phần nối ghép | Với model **giả**, kể cả khi model lỗi thì app vẫn chạy |
| OCR | Đã thử | Chữ **tiếng Anh**. Gói tiếng Việt chưa thử vì máy mình không có |
| Chạy trong PyCharm trên Windows | **Bạn thử** | Bước 1 |
| Gemini / Anthropic / Ollama thật | **Bạn thử** | Bước 2 |
| Embedding bge-m3 thật | **Bạn thử** | Bước 3 |
| Rerank model thật | **Bạn thử** | Bước 4 |
| Chroma với embedding thật | **Bạn thử** | Bước 5 |
| OCR tiếng Việt | **Bạn thử** | Bước 6 |
| Truy cập qua LAN / Radmin VPN | **Bạn thử** | Bước 7 |
| Chất lượng với **quy chế thật** của VKU | **Bạn thử** | Bước 8, quan trọng nhất |

Nên làm theo thứ tự 1 → 2 → 8 trước. Các bước 3 đến 6 là tùy chọn, làm khi cần.

**Khi gặp lỗi, hãy gửi mình:** đoạn chữ đỏ trong tab Run của PyCharm, kèm ảnh chụp trang đang lỗi. Với tài liệu bị chia sai, gửi thêm file đó.

---

## Bước 1. Chạy được trong PyCharm

1. Mở thư mục dự án bằng PyCharm, tạo interpreter **Virtualenv** khi được hỏi.
2. Terminal của PyCharm: `pip install -r requirements.txt`
3. Chuột phải `run.py` > **Run 'run'**. Khi thấy dòng `Uvicorn running on http://127.0.0.1:8000`, mở `http://localhost:8000`.
4. Vào **Quản trị dữ liệu**, tải `samples/quy_che_mau_thu_nghiem.txt`, chọn loại "Quy chế đào tạo".
5. Chờ trạng thái thành **Đã lập chỉ mục**, vào **Hỏi đáp AI**, bấm một gợi ý.

**Đạt khi:** panel nguồn bên phải hiện Điều 5 với các từ khóa được tô vàng.

**Biết server còn chạy không:** tab Run của PyCharm còn hiện chữ "Running" (nút Stop màu đỏ sáng) là còn chạy. Bấm Stop hoặc đóng PyCharm là server tắt; không tự chạy lại khi bật máy. Dữ liệu nằm trong thư mục `data` nên không mất.

| Lỗi thường gặp | Cách xử lý |
|---|---|
| `ModuleNotFoundError` | Chưa cài thư viện hoặc PyCharm đang dùng sai interpreter. Chạy lại `pip install -r requirements.txt` trong Terminal của PyCharm |
| `Address already in use` | Cổng 8000 đang bận. Đặt `APP_PORT=8001` trong `.env` |
| Chữ đỏ về font/mạng khi mở trang | Bình thường nếu mất mạng: font Be Vietnam Pro không tải được, giao diện tự dùng font dự phòng |

## Bước 2. Bật LLM để có câu trả lời

Chọn **một** trong ba cách, sửa file `.env` (tạo bằng cách sao chép `.env.example`), rồi **bấm Stop và Run lại**.

**Cách A, Gemini:** lấy khóa tại aistudio.google.com/apikey.
```
LLM_PROVIDER=gemini
GEMINI_API_KEY=dán-khóa-vào-đây
```

**Cách B, Ollama chạy trên máy bạn (không cần Internet, không mất tiền):**
1. Cài Ollama từ ollama.com, mở CMD gõ `ollama pull qwen2.5:3b`.
2. Trong `.env`:
```
LLM_PROVIDER=openai
OPENAI_BASE_URL=http://localhost:11434/v1
OPENAI_MODEL=qwen2.5:3b
OPENAI_API_KEY=ollama
```

**Cách C, Anthropic:** đặt `LLM_PROVIDER=anthropic` và `ANTHROPIC_API_KEY`.

**Cách thử:** góc dưới trái sidebar phải hiện `LLM: ...` thay cho "Chưa cấu hình LLM". Sau đó hỏi 3 câu:
1. "Điều kiện để xét học bổng là gì?" → phải có câu trả lời kèm [1], [2].
2. "Ký túc xá có wifi không?" (không có trong văn bản) → phải hiện khung vàng "Chưa tìm thấy thông tin đủ căn cứ".
3. Hỏi tiếp "còn điểm rèn luyện thì sao?" → phải trả lời đúng ngữ cảnh học bổng.

**Đạt khi:** cả ba đúng. Nếu câu 2 bị trả lời bịa, gửi mình câu hỏi và câu trả lời.

| Lỗi | Nguyên nhân |
|---|---|
| Khung đỏ "LLM trả về lỗi 404" | Tên model sai hoặc đã đổi. Xem tên model hiện hành ở trang của nhà cung cấp |
| "lỗi 401/403" | Khóa API sai hoặc chưa kích hoạt |
| "lỗi 429" | Hết hạn mức miễn phí, chờ một lúc rồi thử lại |
| "Không kết nối được tới dịch vụ LLM" | Mất mạng, hoặc Ollama chưa chạy |

## Bước 3. Embedding ngữ nghĩa (bge-m3), tùy chọn

Giúp tìm được câu hỏi dùng từ khác văn bản (ví dụ hỏi "trượt môn" mà quy chế viết "học phần chưa đạt").

1. Terminal của PyCharm: `pip install sentence-transformers`
2. Trong `.env`: `EMBEDDING_MODEL=BAAI/bge-m3`
3. Run lại. **Lần đầu tải model khoảng 2 GB**, mất vài phút.
4. Vào **Quản trị dữ liệu**, bấm **Lập lại** ở từng tài liệu đã có (tài liệu cũ chưa có vector).
5. Mở `http://localhost:8000/api/health`, phải thấy `"semantic_search": true`.

**Cách thử:** hỏi "Trượt môn thì phải làm gì?" (mẫu thử nghiệm viết "chưa đạt", "học lại"). Nếu tìm đúng Điều 4 là đạt. Thử cùng câu đó khi tắt `EMBEDDING_MODEL` để so sánh.

**Máy yếu:** nếu báo hết bộ nhớ hoặc chạy chậm, đổi sang model nhỏ hơn như `paraphrase-multilingual-MiniLM-L12-v2`, rồi **Lập lại** tài liệu. Bản `pip` mặc định trên Windows thường chạy bằng CPU, chậm hơn nhưng vẫn dùng được.

## Bước 4. Rerank, tùy chọn

Cần đã cài `sentence-transformers` (Bước 3, mục 1). Trong `.env`: `RERANK_MODEL=BAAI/bge-reranker-v2-m3`, Run lại. Lần đầu hỏi sẽ chậm vì tải model.

**Cách thử:** chuẩn bị 5 câu hỏi, ghi lại nguồn [1] khi tắt rerank và khi bật rerank. Rerank tốt khi nguồn [1] đúng nhiều hơn.

**Nếu model lỗi:** tab Run in `Rerank thất bại, bỏ qua bước rerank`, app **vẫn hoạt động** bình thường, chỉ không có rerank.

## Bước 5. Chroma, tùy chọn

Cần Bước 3 đã chạy tốt.

1. `pip install chromadb`
2. Trong `.env`: `VECTOR_STORE=chroma`
3. Run lại, vào **Quản trị dữ liệu**, **Lập lại** tất cả tài liệu.
4. Kiểm tra: thư mục `data/chroma` xuất hiện, và `http://localhost:8000/api/health` có `"vector_store": "chroma"`.
5. Xóa thử một tài liệu rồi hỏi lại, nguồn của tài liệu đó phải biến mất.

Đổi qua lại giữa `sqlite` và `chroma` luôn phải **Lập lại** tài liệu.

## Bước 6. OCR cho PDF scan, tùy chọn

1. Tải Tesseract cho Windows tại github.com/UB-Mannheim/tesseract/wiki. Trong trình cài đặt, mục **Additional language data**, **tick "Vietnamese"**. Đường dẫn mặc định thường là `C:\Program Files\Tesseract-OCR\`.
2. Kiểm tra: mở CMD gõ `"C:\Program Files\Tesseract-OCR\tesseract.exe" --list-langs`. Danh sách phải có `vie`.
3. `pip install pypdfium2 pytesseract pillow`
4. Trong `.env`:
   ```
   OCR=1
   OCR_LANG=vie+eng
   TESSERACT_CMD=C:\Program Files\Tesseract-OCR\tesseract.exe
   ```
5. Run lại, tải một **PDF scan** (hoặc in một văn bản ra PDF dạng ảnh) lên.

**Đạt khi:** tài liệu chuyển thành "Đã lập chỉ mục" kèm huy hiệu "Cảnh báo chất lượng" ghi rằng văn bản được nhận dạng bằng OCR. Mở trang **Thư viện văn bản**, xem chi tiết và đọc thử vài Điều để đánh giá độ chính xác chữ tiếng Việt.

| Thông báo | Ý nghĩa |
|---|---|
| "Tesseract chưa có gói ngôn ngữ: vie" | Chưa tick Vietnamese lúc cài. Chạy lại trình cài đặt |
| "Không tìm thấy chương trình Tesseract" | Sai đường dẫn `TESSERACT_CMD` |
| "OCR đang tắt" | Chưa đặt `OCR=1` |

OCR luôn có sai sót (số, dấu). Với văn bản quan trọng nên dùng bản PDF/DOCX gốc thay vì bản scan.

## Bước 7. Truy cập qua LAN / Radmin VPN

1. Trong `.env`: `APP_HOST=0.0.0.0` và đặt `ADMIN_PASSWORD` mạnh trước lần chạy đầu (mật khẩu quản trị viên). Người khác vào sẽ phải đăng ký hoặc được cấp tài khoản. Run lại.
2. Mở CMD gõ `ipconfig`, lấy IPv4 (hoặc IP của Radmin VPN, thường dạng `26.x.x.x`).
3. Máy khác vào `http://<IP>:8000`.
4. Lần đầu Windows hỏi tường lửa thì chọn **Allow** cho mạng Private.

**Đạt khi:** điện thoại cùng WiFi mở được trang, hỏi được, và vào trang Quản trị phải đòi mật khẩu.

Lưu ý: lịch sử hội thoại gắn với từng trình duyệt, hai người dùng chung máy sẽ thấy lịch sử của nhau.

## Bước 8. Thử với quy chế thật (quan trọng nhất)

Các ngưỡng lọc mình chỉnh theo tài liệu mẫu nhỏ nên **phải chỉnh lại bằng quy chế thật**.

1. Tải **một** quy chế thật của VKU (ưu tiên DOCX hoặc PDF xuất từ Word). Điền số hiệu, ngày ban hành, hiệu lực.
2. Vào **Thư viện văn bản**, xem chi tiết. **Kiểm tra chia Điều**: danh sách các Điều có đúng với văn bản không? Có Điều nào bị dính vào nhau hoặc bị mất không?
3. Soạn 10 câu hỏi có đáp án trong quy chế, và 3 câu không có đáp án. Hỏi từng câu và ghi kết quả:

| Hiện tượng | Chỉnh trong `.env` |
|---|---|
| Câu có đáp án mà báo "Chưa tìm thấy thông tin" | Giảm `MIN_COVERAGE` (ví dụ 0.4 → 0.3) |
| Câu ngoài phạm vi mà vẫn trả lời | Tăng `MIN_COVERAGE` (ví dụ 0.4 → 0.5) |
| Nguồn xếp sau toàn đoạn không liên quan | Tăng `REL_SCORE` (0.45 → 0.6) |
| Thiếu nguồn cần thiết | Giảm `REL_SCORE` hoặc tăng `TOP_K` |

Mỗi lần sửa `.env` phải Run lại server.

4. **Nếu Điều bị chia sai** (ví dụ quy chế ghi "Điều 5 -" hoặc "ĐIỀU 5" mà hệ thống không nhận), gửi mình file đó, mình sẽ chỉnh bộ chia đoạn.
5. Nếu có hai phiên bản của cùng một quy chế, tải cả hai, đặt hiệu lực đúng, rồi hỏi: bản còn hiệu lực phải đứng trước và có khung cảnh báo nhiều phiên bản.
