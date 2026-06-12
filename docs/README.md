# SPD Machine Info Display

Hiển thị **Machine ID**, **Status**, **Server Name** trên Fluidd/Mainsail Console.

## Kiến trúc

```
SPDKlipper Plugin (socket_manager.py)
  └── viết spd_status.json (machine_id, machine_name, connected, status)
         │
         ▼
spd_machine_info.py (Klipper extra module)
  └── đọc spd_status.json mỗi 5 giây
         │
         ├── printer["spd_machine_info"].machine_id
         ├── printer["spd_machine_info"].status
         ├── printer["spd_machine_info"].connected
         │
         ▼
[gcode_macro MACHINE_INFO] → RESPOND → Fluidd Console
[delayed_gcode MACHINE_INFO_STARTUP] → tự động chạy 10s sau Klipper start
```

**Luồng dữ liệu:**
1. Plugin (`socket_manager.py`) ghi file `spd_status.json` mỗi khi trạng thái kết nối thay đổi
2. Klipper extra module (`spd_machine_info.py`) đọc file này mỗi 5 giây
3. Dữ liệu có sẵn trong macro qua `printer["spd_machine_info"].machine_id`
4. `MACHINE_INFO` macro hiển thị lên Console Fluidd qua `RESPOND`

## Cài đặt

### Cách 1: Tự động (dùng install.sh)

```bash
cd ~/spdklipper-plugin
./scripts/install.sh
```

Script sẽ tự động:
- Copy `spd_machine_info.py` vào `~/klipper/klippy/extras/`
- Copy `spd_machine_info.cfg` vào thư mục config
- Thêm `[include spd_machine_info.cfg]` vào `printer.cfg`
- Restart Klipper

### Cách 2: Thủ công

```bash
# 1. Copy Klipper extra module
cp ~/spdklipper-plugin/scripts/spd_machine_info.py ~/klipper/klippy/extras/spd_machine_info.py

# 2. Copy macro config
cp ~/spdklipper-plugin/scripts/spd_machine_info.cfg ~/printer_data/config/spd_machine_info.cfg

# 3. Thêm vào printer.cfg
echo -e "\n[include spd_machine_info.cfg]" >> ~/printer_data/config/printer.cfg

# 4. Restart Klipper
sudo systemctl restart klipper
```

---

## Cách dùng

### Trên Fluidd/Mainsail

| Cách | Mô tả |
|------|-------|
| **Tự động** | 10s sau khi Klipper restart, macro tự chạy — info hiện trong Console |
| **Macro Button** | Settings → Macros → Add `MACHINE_INFO` → kéo ra dashboard → click để xem |
| **Console** | Gõ `MACHINE_INFO` để xem |

### Dữ liệu tự động

- **Machine ID**: Lấy từ plugin API (`/machine/info`), hiển thị số nhận dạng máy
- **Status**: `● CONNECTED` hoặc `○ DISCONNECTED` dựa trên trạng thái kết nối socket
- **Server**: Hostname của Raspberry Pi

Tất cả dữ liệu được cập nhật tự động mỗi 5 giây.

---

## Yêu cầu

- SPDKlipper plugin đang chạy (có file `spd_status.json` trong thư mục config)
- Klipper đã cài đặt (có thư mục `~/klipper/klippy/extras/`)
- File `spd_machine_info.cfg` được include trong `printer.cfg`

---

## File liên quan

| File | Vai trò |
|------|---------|
| [`scripts/spd_machine_info.py`](../scripts/spd_machine_info.py) | Klipper extra module (đọc spd_status.json, expose printer objects) |
| [`scripts/spd_machine_info.cfg`](../scripts/spd_machine_info.cfg) | Klipper config ([spd_machine_info] + MACHINE_INFO macro) |
| [`libs/socket_manager.py`](../libs/socket_manager.py) | Plugin socket manager (ghi spd_status.json) |
| [`plugin/main.py`](../plugin/main.py) | FastAPI server + `/machine/info` endpoint |
