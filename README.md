# SPD Klipper Plugin (SePrinder Klipper Plugin)

SPD Klipper Plugin là phần mềm trung gian (agent) đóng vai trò kết nối trực tiếp các máy in 3D với hệ thống máy chủ **SPD Server** và **SPD Connect** trong hệ sinh thái SePrinder.

## 1. Giới thiệu

Hệ thống được thiết kế để chạy trực tiếp trên các bộ giải pháp kết nối (như Raspberry Pi, Orange Pi hoặc máy tính Windows) gần máy in. SPD Klipper Plugin chịu trách nhiệm:

- **Giám sát thời gian thực**: Theo dõi trạng thái in, nhiệt độ và tiến độ của máy in 3D.
<!-- - **Phát hiện lỗi bằng AI**: Tích hợp mô hình học máy để tự động phát hiện các lỗi in (như "spaghetti", bong bàn in) thông qua camera. -->
- **Điều khiển từ xa**: Nhận lệnh từ SPD Server (qua SPD Connect) để bắt đầu, tạm dừng hoặc hủy lệnh in.
- **Quản lý dữ liệu cục bộ**: Lưu trữ cấu hình và log hoạt động thông qua cơ sở dữ liệu SQLite tích hợp.

---

## 2. Công nghệ sử dụng

- **Ngôn ngữ**: Python 3.11+
- **Framework**: FastAPI (Web Server & API)
- **Real-time**: Socket.io (Kết nối đến SPD Connect)
- **AI/ML**: ONNX Runtime (Xử lý mô hình phát hiện lỗi)
- **CSDL**: SQLModel (SQLite)
- **Giao diện**: Jinja2 + TailwindCSS

---

## 3. Hướng dẫn Cài đặt

### Yêu cầu hệ thống
- Python 3.11 hoặc cao hơn.
<!-- - Camera USB hoặc CSI (nếu dùng tính năng AI). -->
- Kết nối internet ổn định.

### Cài đặt môi trường (Local)

1. **Khởi tạo môi trường ảo**:
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # Linux/Mac
   .venv\Scripts\activate     # Windows
   ```

2. **Cài đặt thư viện**:
   Tùy thuộc vào kiến trúc máy tính của bạn, chọn file requirements tương ứng:
   - **Windows 64-bit**: `pip install -r requirements-win64.txt`
   - **Raspberry Pi 4/5 (64-bit)**: `pip install -r requirements-aarch64.txt`
   - **Raspberry Pi cũ (32-bit)**: `pip install -r requirements-armv7l.txt`

3. **Cấu hình biến môi trường**:
   Sao chép file `.env.example` thành `.env` và điền các thông tin cần thiết (URL Server, API Key...).

4. **Khởi chạy**:
   ```bash
   python main.py
   ```
   Sau khi chạy, bạn có thể truy cập giao diện quản lý cục bộ tại: `http://localhost:1122`

---

## 4. Triển khai với Docker

Nếu bạn muốn chạy SPD Bridge trong môi trường container:

**Build Image:**
```bash
docker compose build
```

**Khởi chạy:**
```bash
docker compose up -d
```

---

## 5. Cấu trúc Thư mục

- `/src`: Mã nguồn chính (Điều khiển máy in, xử lý socket, view).
<!-- - `/detection`: Chứa các mô hình AI và dữ liệu phục vụ phát hiện lỗi. -->
- `/static` & `/src/templates`: Giao diện người dùng cục bộ.
- `main.py`: Điểm khởi đầu của ứng dụng.

---
*Phát triển bởi đội ngũ SePrinder - Giải pháp thông minh cho in 3D công nghiệp.*
