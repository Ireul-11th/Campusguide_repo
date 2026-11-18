"""Chạy server trong PyCharm: chuột phải file này > Run 'run'.

Mở http://localhost:8000. Cấu hình (HOST, PORT, khóa API...) nằm trong file .env.
Sửa code trong thư mục app/ rồi lưu thì server tự khởi động lại.
"""
import uvicorn

from app import config

if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host=config.HOST,
        port=config.PORT,
        reload=True,
        reload_dirs=[str(config.BASE_DIR / "app")],
    )
