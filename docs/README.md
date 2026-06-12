# SPD Machine Info Display

Hiển thị **Machine ID**, **Status**, **Last Seen** trên Fluidd/Mainsail mà không sửa source code.

---

## Cài đặt

### Cách 1: Tự động (dùng install.sh)

```bash
cd ~/spdklipper-plugin
./scripts/install.sh
```

Script sẽ tự động:
- Copy Moonraker component (`spd_status.py`)
- Copy Klipper macros (`spd_machine_info.cfg`)
- Thêm `[spd_status]` vào `moonraker.conf`
- Thêm `[include spd_machine_info.cfg]` vào `printer.cfg`
- Restart Moonraker + Klipper

### Cách 2: Thủ công (nếu đã có plugin)

```bash
# 1. Copy Moonraker component
cp ~/spdklipper-plugin/scripts/moonraker_spd_status.py ~/moonraker/moonraker/components/spd_status.py

# 2. Copy Klipper macro
cp ~/spdklipper-plugin/scripts/spd_machine_info.cfg ~/printer_data/config/spd_machine_info.cfg

# 3. Thêm vào moonraker.conf
echo -e "\n[spd_status]" >> ~/printer_data/config/moonraker.conf

# 4. Thêm vào printer.cfg
echo -e "\n[include spd_machine_info.cfg]" >> ~/printer_data/config/printer.cfg

# 5. Restart
sudo systemctl restart moonraker
sudo systemctl restart klipper
```

---

## Cách dùng

### Trên Fluidd/Mainsail

| Cách | Mô tả |
|------|-------|
| **Status Bar** (tự động) | Góc trên bên phải: `SPD \| ID:88S175... \| CONNECTED \| Last:12:34:57` |
| **Console** | Gõ `DISPLAY_SPD_INFO` để xem chi tiết |
| **Macro Button** | Settings → Macros → Add `DISPLAY_SPD_INFO` → kéo ra dashboard |

### API

```bash
# Moonraker API
curl http://localhost:7125/server/spd_status/info

# SPDKlipper Plugin API
curl http://localhost:1122/machine/info
```

### Monitor script

```bash
python3 ~/spdklipper-plugin/scripts/spd_monitor.py --watch
```

---

## Gỡ cài đặt

```bash
# 1. Xóa Moonraker component
rm ~/moonraker/moonraker/components/spd_status.py

# 2. Xóa Klipper macro
rm ~/printer_data/config/spd_machine_info.cfg

# 3. Xóa khỏi moonraker.conf (dùng nano hoặc sed)
sed -i '/\[spd_status\]/d' ~/printer_data/config/moonraker.conf

# 4. Xóa khỏi printer.cfg
sed -i '/spd_machine_info.cfg/d' ~/printer_data/config/printer.cfg

# 5. Restart
sudo systemctl restart moonraker
sudo systemctl restart klipper
```

---

## File liên quan

| File | Vai trò |
|------|---------|
| [`scripts/moonraker_spd_status.py`](../scripts/moonraker_spd_status.py) | Moonraker component (API + display_status + database) |
| [`scripts/spd_machine_info.cfg`](../scripts/spd_machine_info.cfg) | Klipper macros (tự động cập nhật mỗi 30s) |
| [`plugin/main.py`](../plugin/main.py) | FastAPI server + `/machine/info` endpoint |
| [`scripts/spd_monitor.py`](../scripts/spd_monitor.py) | CLI monitor script |
