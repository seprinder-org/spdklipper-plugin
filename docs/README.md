# SPD Machine Info Display

Hiển thị **Machine ID**, **Status**, **Last Seen** trên Fluidd/Mainsail thông qua Macro Group.

## Kiến trúc

```
SPDKlipper Plugin (/machine/info)
        │
        ▼
Moonraker machine_status component (Python aiohttp, mỗi 10s)
        │
        ├── Moonraker database namespace: machine_info
        │
        └── Klipper save_variables (variable: spd_machine_info)
                │
                ▼
SPD_MACHINE_INFO macro → RESPOND → Fluidd Console
```

## Cài đặt

### Cách 1: Tự động (dùng install.sh)

```bash
cd ~/spdklipper-plugin
./scripts/install.sh
```

Script sẽ tự động:
- Copy Moonraker component (`machine_status.py`)
- Copy Klipper macro (`spd_machine_info.cfg`)
- Thêm `[machine_status]` vào `moonraker.conf`
- Thêm `[save_variables]` và `[include spd_machine_info.cfg]` vào `printer.cfg`
- Restart Moonraker + Klipper

### Cách 2: Thủ công (nếu đã có plugin)

```bash
# 1. Copy Moonraker component
cp ~/spdklipper-plugin/scripts/machine_status.py ~/moonraker/moonraker/components/machine_status.py

# 2. Copy Klipper macro
cp ~/spdklipper-plugin/scripts/spd_machine_info.cfg ~/printer_data/config/spd_machine_info.cfg

# 3. Thêm vào moonraker.conf
echo -e "\n[machine_status]" >> ~/printer_data/config/moonraker.conf

# 4. Thêm vào printer.cfg (cần [save_variables] để SPD_MACHINE_INFO macro hoạt động)
echo -e "\n[save_variables]\nfilename: ~/printer_data/config/save_variables.cfg" >> ~/printer_data/config/printer.cfg
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
| **Macro Button** | Settings → Macros → Add `SPD_MACHINE_INFO` → kéo ra dashboard → click để xem Machine ID, Status, Last Seen |
| **Console** | Gõ `SPD_MACHINE_INFO` để xem chi tiết |

### API

```bash
# Moonraker API (từ machine_status component)
curl http://localhost:7125/server/machine_status/info

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
rm ~/moonraker/moonraker/components/machine_status.py

# 2. Xóa Klipper macro
rm ~/printer_data/config/spd_machine_info.cfg

# 3. Xóa khỏi moonraker.conf
sed -i '/\[machine_status\]/d' ~/printer_data/config/moonraker.conf

# 4. Xóa khỏi printer.cfg
sed -i '/spd_machine_info.cfg/d' ~/printer_data/config/printer.cfg
# Lưu ý: Chỉ xóa [save_variables] nếu không có macro nào khác dùng nó

# 5. Restart
sudo systemctl restart moonraker
sudo systemctl restart klipper
```

---

## File liên quan

| File | Vai trò |
|------|---------|
| [`scripts/machine_status.py`](../scripts/machine_status.py) | Moonraker component (fetch API → save_variables) |
| [`scripts/spd_machine_info.cfg`](../scripts/spd_machine_info.cfg) | Klipper macro (đọc save_variables → hiển thị) |
| [`plugin/main.py`](../plugin/main.py) | FastAPI server + `/machine/info` endpoint |
| [`scripts/spd_monitor.py`](../scripts/spd_monitor.py) | CLI monitor script |
