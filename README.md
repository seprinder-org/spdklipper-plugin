# SPD Klipper Plugin (SePrinder Klipper Plugin)

SPD Klipper Plugin là phần mềm trung gian (agent) đóng vai trò kết nối trực tiếp các máy in 3D với hệ thống máy chủ **SPD Server** và **SPD Connect** trong hệ sinh thái SePrinder.

## Tính năng

- **Giám sát thời gian thực**: Theo dõi trạng thái in, nhiệt độ và tiến độ của máy in 3D.
- **Điều khiển từ xa**: Nhận lệnh từ SPD Server để bắt đầu, tạm dừng hoặc hủy lệnh in.
- **Quản lý dữ liệu cục bộ**: Lưu trữ cấu hình và log hoạt động thông qua cơ sở dữ liệu SQLite tích hợp.
- **Tự động kết nối lại**: Tự động kết nối socket khi mất kết nối.
- **Tích hợp Moonraker**: Hỗ trợ restart plugin qua Moonraker API và macro `RESTART_SPDK`.

---

## Yêu cầu hệ thống

- **Hệ điều hành**: Raspberry Pi OS / Ubuntu / Debian (hoặc hệ thống dựa trên Debian khác)
- **Python**: 3.11 trở lên
- **Klipper + Moonraker**: Đã cài đặt và hoạt động
- **Kết nối Internet**: Ổn định để kết nối đến SPD Server

---

## Cài đặt

### 1. Clone repository

```bash
cd ~
git clone https://github.com/seprinder-org/spdklipper-plugin.git
cd spdklipper-plugin
```

### 2. Chạy script cài đặt

```bash
./scripts/install.sh
```

Script sẽ thực hiện các bước sau:
- Cài đặt các gói hệ thống cần thiết (Python virtualenv, ffmpeg, libjpeg, ...)
- Tạo môi trường ảo Python (`~/spdklipper-plugin-env`)
- Cài đặt các thư viện Python từ `scripts/requirements.txt`
- Tạo systemd service (`spdklipper-plugin.service`)
- Tạo file cấu hình mặc định (`~/printer_data/config/spdklipper.conf`)
- Thêm cấu hình update manager vào `moonraker.conf`
- Thêm macro `RESTART_SPDK` và `FIRMWARE_RESTART` vào `printer.cfg`
- Thêm `spdklipper-plugin` vào `moonraker.asvc`
- Phân quyền bảo mật cho các file nhạy cảm

### 3. Cấu hình

Chỉnh sửa file cấu hình:

```bash
nano ~/printer_data/config/spdklipper.conf
```

Cấu hình các thông tin sau:

```ini
[server]
server: localhost

[credentials]
# Thông tin tài khoản SPD để tự động đăng nhập
username: email@example.com
password: your_password
machine_id: your_machine_identify_number
```

> **Cách lấy Machine ID**: Đăng nhập vào [https://seprinder.com](https://seprinder.com) → Vào trang cá nhân → Mục Machines → Sao chép "Identify Number" của máy in.

### 4. Khởi động dịch vụ

```bash
sudo systemctl restart moonraker
sudo systemctl restart klipper
sudo systemctl start spdklipper-plugin
```

Kiểm tra trạng thái:

```bash
sudo systemctl status spdklipper-plugin
```

### 5. Truy cập giao diện quản lý

Mở trình duyệt và truy cập: `http://<địa-chỉ-pi>:1122`

---

## Sử dụng

### Macro Klipper

Plugin cài đặt các macro sau vào `printer.cfg`:

| Macro | Mô tả |
|-------|-------|
| `RESTART_SPDK` | Khởi động lại dịch vụ SPDKlipper plugin (chạy từ console) |
| `FIRMWARE_RESTART` | Ghi đè macro mặc định — khởi động lại firmware + SPDKlipper plugin |

#### RESTART_SPDK

Khởi động lại riêng dịch vụ SPDKlipper plugin:

```
RESTART_SPDK
```

Chạy từ console Fluidd/Mainsail hoặc gọi từ macro khác.

#### FIRMWARE_RESTART (tích hợp sẵn)

Khi nhấn nút **"Restart Firmware"** trong Fluidd/Mainsail, macro này sẽ tự động:
1. Dừng dịch vụ `spdklipper-plugin` qua Moonraker API
2. Chờ 2 giây để plugin tắt sạch
3. Thực hiện khởi động lại firmware Klipper

Sau đó systemd sẽ tự động khởi động lại plugin.

### Giao diện Web

Truy cập `http://<địa-chỉ-pi>:1122` để:
- Đăng nhập bằng tài khoản SPD
- Xem trạng thái kết nối socket
- Xem log hoạt động
- Kết nối/ngắt kết nối socket thủ công

### Cập nhật plugin

Plugin hỗ trợ cập nhật qua Moonraker update manager. Trong Fluidd/Mainsail:
1. Vào **Machine** → **Update Manager**
2. Tìm **spdklipper-plugin**
3. Nhấn **Update**

Hoặc thủ công:

```bash
cd ~/spdklipper-plugin
git pull
sudo systemctl restart spdklipper-plugin
```

### Bảo mật file .env

Plugin cung cấp script mã hóa file `.env` để bảo vệ thông tin nhạy cảm:

```bash
# Mã hóa .env
./scripts/secure_env.sh lock

# Giải mã .env
./scripts/secure_env.sh unlock

# Kiểm tra trạng thái
./scripts/secure_env.sh status
```

---

## Gỡ cài đặt

### Sử dụng script uninstall

```bash
cd ~/spdklipper-plugin
./scripts/uninstall.sh
```

Script sẽ:
1. Dừng và xóa tất cả systemd service `spdklipper-plugin*`
2. Xóa thư mục môi trường ảo Python (`~/spdklipper-plugin-env`)
3. Xóa file cấu hình (`~/printer_data/config/spdklipper*.conf`)
4. Xóa file log (`~/printer_data/logs/spdklipper*`)
5. Xóa cấu hình sysctl (`/etc/sysctl.d/51-dmesg-restrict.conf`)
6. Xóa các file nhạy cảm (`.env`, `.env.enc`, `db.sqlite3`)

> **Lưu ý**: Thư mục dự án (`~/spdklipper-plugin`) sẽ **không** bị xóa. Để xóa hoàn toàn, chạy thêm:
> ```bash
> rm -rf ~/spdklipper-plugin
> ```

### Dọn dẹp thủ công các cấu hình Moonraker/Klipper

Sau khi uninstall, bạn nên xóa thủ công các cấu hình đã thêm vào Moonraker và Klipper:

**1. Xóa macro khỏi `printer.cfg`:**

```bash
nano ~/printer_data/config/printer.cfg
```

Xóa các macro sau:
```ini
[gcode_macro RESTART_SPDK]
...
[gcode_macro FIRMWARE_RESTART]
...
```

**2. Xóa update manager khỏi `moonraker.conf`:**

```bash
nano ~/printer_data/config/moonraker.conf
```

Xóa phần:
```ini
[update_manager client spdklipper-plugin]
...
```

**3. Xóa `spdklipper-plugin` khỏi `moonraker.asvc`:**

```bash
nano ~/printer_data/moonraker.asvc
```

Xóa dòng `spdklipper-plugin`.

**4. Khởi động lại Moonraker:**

```bash
sudo systemctl restart moonraker
```

---

## Cấu trúc thư mục

```
spdklipper-plugin/
├── plugin/
│   └── main.py              # Điểm khởi đầu ứng dụng (FastAPI)
├── src/
│   ├── controller/           # Controller layer (gọi API đến SPD Server)
│   ├── database/             # SQLite database models
│   ├── library/              # Handler, config reader, exception
│   ├── model/                # Data models
│   ├── printer/              # Printer implementations (Klipper, ...)
│   ├── public/               # Static assets (favicon, ...)
│   └── view/                 # Jinja2 templates (HTML)
├── libs/
│   └── socket_manager.py     # Socket.IO client quản lý kết nối
├── constants/
│   └── constant.py           # Hằng số cấu hình
├── scripts/
│   ├── install.sh            # Script cài đặt
│   ├── uninstall.sh          # Script gỡ cài đặt
│   ├── secure_env.sh         # Mã hóa/giải mã .env
│   └── requirements.txt      # Python dependencies
├── static/                   # CSS (TailwindCSS)
├── tailwindcss/              # TailwindCSS source
└── utils/                    # Utility functions
```

---

## Khắc phục sự cố

| Vấn đề | Nguyên nhân | Giải pháp |
|--------|-------------|-----------|
| Plugin không kết nối được socket | Sai HOST_CONNECT | Kiểm tra `constant.py` hoặc `.env` |
| `RESTART_SPDK` không hoạt động | Plugin chưa có trong `moonraker.asvc` | Thêm `spdklipper-plugin` vào `~/printer_data/moonraker.asvc` |
| Lỗi `action_call_remote_method` | Moonraker chưa bật authorization | Thêm `[authorization] enabled: false` vào `moonraker.conf` |
| Plugin không tự động đăng nhập | Thiếu thông tin trong `spdklipper.conf` | Điền đủ `username`, `password`, `machine_id` |
| Cổng 1122 đã được sử dụng | Ứng dụng khác đang dùng cổng | Plugin tự động tăng cổng nếu cổng đã được sử dụng |

---

*Phát triển bởi đội ngũ SePrinder - Giải pháp thông minh cho in 3D công nghiệp.*
