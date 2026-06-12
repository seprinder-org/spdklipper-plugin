# SPD Machine Info Display

Hiển thị **Machine ID**, **Status**, **Server Name** trên Fluidd/Mainsail Console.

## Kiến trúc

Giải pháp **100% Klipper config** — không cần Moonraker component, không cần Python code trên Klipper.

```
[shell_command _FETCH_MACHINE_INFO]  →  curl + python3 → plugin API (/machine/info)
        ↓
[gcode_macro MACHINE_INFO]  →  RUN_SHELL_COMMAND → parse pipe-delimited → RESPOND
        ↓
[delayed_gcode MACHINE_INFO_STARTUP]  →  tự động chạy 10s sau khi Klipper khởi động
```

**Luồng dữ liệu:**
1. `[shell_command _FETCH_MACHINE_INFO]` chạy `curl` gọi API `http://127.0.0.1:1122/machine/info`
2. `python3` parse JSON, xuất ra pipe-delimited: `machine_id|machine_name|connected|status`
3. `MACHINE_INFO` macro parse kết quả bằng `raw.split("|")` trong Jinja2
4. Hiển thị lên Console Fluidd qua `RESPOND`

## Cài đặt

### Cách 1: Tự động (dùng install.sh)

```bash
cd ~/spdklipper-plugin
./scripts/install.sh
```

Script sẽ tự động:
- Copy `spd_machine_info.cfg` vào thư mục config
- Thêm `[include spd_machine_info.cfg]` vào `printer.cfg`
- Restart Klipper

### Cách 2: Thủ công

```bash
# 1. Copy macro file
cp ~/spdklipper-plugin/scripts/spd_machine_info.cfg ~/printer_data/config/spd_machine_info.cfg

# 2. Thêm vào printer.cfg
echo -e "\n[include spd_machine_info.cfg]" >> ~/printer_data/config/printer.cfg

# 3. Restart Klipper
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

### Machine ID tự động

Machine ID được lấy **tự động** từ SPDKlipper plugin API (`/machine/info`), không cần cấu hình thủ công.

Nếu bạn muốn ghi đè Machine ID hiển thị, sửa trong file `~/printer_data/config/spd_machine_info.cfg` tại dòng `[shell_command _FETCH_MACHINE_INFO]` — thay đổi URL hoặc tham số nếu cần.

---

## Yêu cầu

- SPDKlipper plugin đang chạy (cung cấp API `/machine/info` trên port 1122)
- `curl` và `python3` đã được cài đặt trên Raspberry Pi
- File `spd_machine_info.cfg` được include trong `printer.cfg`

---

## File liên quan

| File | Vai trò |
|------|---------|
| [`scripts/spd_machine_info.cfg`](../scripts/spd_machine_info.cfg) | Klipper macro (shell_command + MACHINE_INFO + delayed_gcode) |
| [`plugin/main.py`](../plugin/main.py) | FastAPI server + `/machine/info` endpoint |
