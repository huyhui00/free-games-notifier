# Free Games Notifier 🎮

ระบบแจ้งเตือนเกมฟรีจาก Epic Games และ Steam ไปยัง Discord Webhook ทั้งวัน ทั้งคืน

##  ฟีเจอร์

-  **ตรวจสอบเกมฟรี** - Epic Games Store และ Steam Store
-  **Discord Notifications** - แจ้งเตือนไปยัง Discord พร้อมภาพและรายละเอียด
-  **Polling Loop** - ตรวจสอบอัตโนมัติทุกวัน 22:01 น. เวลาไทย (GitHub Actions)
-  **ไม่แจ้งซ้ำ** - ระบบ Dedup ที่ติดตาม promotion period
-  **Status Embed** - แสดงสถานะของแต่ละแพลตฟอร์ม
-  **Rich Format** - Embed พร้อมรูป ราคา คะแนน และแท็ก

##  เกมที่ตรวจสอบ

### Epic Games
- **ประเภท:** เกมแจกฟรีชั่วคราว (จำกัดเวลา)
- **ฟิลเตอร์:** 
  - ต้องมีราคาเดิม > 0
  - discount = 0% (ฟรีจริง ไม่ใช่ sale)
  - ปัจจุบัน (ไม่ใช่ upcoming)

### Steam
- **ประเภท:** เกมแจกฟรีชั่วคราว
- **ฟิลเตอร์:**
  - ราคาปกติ > 0
  - ราคาปัจจุบัน = 0
  - Fallback: ยอมรับเกมจากการค้นหา `maxprice=free`

##  ความต้องการ

- **Python 3.7+** (ทดสอบด้วย 3.14)
- **requests library**
- **Discord Webhook URL**

##  ติดตั้ง & ใช้งาน

### 1. Clone หรือ Download
```bash
git clone <repository-url>
cd free-games-notifier
```

### 2. ติดตั้ง Dependencies
```bash
pip install -r requirements.txt
```

### 3. ตั้ง Environment Variables

**Local Testing:**
```powershell
# PowerShell
$env:DISCORD_WEBHOOK_URL = "https://discord.com/api/webhooks/..."
$env:RUN_ONCE = "1"
py -3 notify.py
```

**Linux/Mac:**
```bash
export DISCORD_WEBHOOK_URL="https://discord.com/api/webhooks/..."
export RUN_ONCE="1"
python3 notify.py
```

### 4. รันสคริปต์
```bash
# ทั้งวัน (polling loop)
python3 notify.py

# ครั้งเดียว
RUN_ONCE=1 python3 notify.py

# ด้วย Debug logs
DEBUG=1 python3 notify.py
```

##  Environment Variables

| ตัวแปร | ค่าเริ่มต้น | คำอธิบาย |
|--------|-----------|---------|
| `DISCORD_WEBHOOK_URL` | - | **จำเป็น** - Discord Webhook URL |
| `RUN_ONCE` | 0 | 0 = loop ตลอด, 1 = รันครั้งเดียว |
| `POLL_INTERVAL` | 600.6 | วินาทีระหว่างการตรวจสอบ (10.01 นาที) |
| `DEBUG` | 0 | 0 = ปกติ, 1 = แสดง skip reasons |
| `NOTIFY_UPCOMING` | 0 | 0 = ข้ามเกมที่มาเร็วๆ นี้, 1 = แจ้งด้วย |
| `WEBHOOK_MAX_RETRIES` | 3 | จำนวนครั้ง retry เมื่อ Discord ตอบ 429/5xx หรือเกิด network error |
| `WEBHOOK_RETRY_BASE` | 1.5 | เวลาฐาน (วินาที) สำหรับ exponential backoff |
| `NOTIFIED_FILE` | notified.json | ไฟล์เก็บ dedup IDs |
| `STATUS_FILE` | status.json | ไฟล์เก็บสถานะแพลตฟอร์ม |

##  สถาปัตยกรรม Dedup (ป้องกันการแจ้งซ้ำ)

### Epic Games
```
ID format: epic:{slug}:{YYYYMMDD}
Example:   epic:fortnite:20260619
```
- ต่างครั้ง = `startDate` ต่างกัน = ID ต่างกัน → **จะแจ้งอีก** ✓

### Steam
```
ID format: steam:{appid}
Example:   steam:1180660
```
- ใช้ appid (Steam API ไม่มี promotion period)

**ไฟล์ dedup:**
```json
{
  "ids": [
    "epic:fortnite:20260619",
    "steam:1180660"
  ]
}
```

##  Discord Integration

### Setup Webhook
1. Discord Server → Settings → Webhooks
2. Create Webhook → Copy URL
3. ตั้ง `DISCORD_WEBHOOK_URL` environment variable

### Message Format
- **Game Embed:** ชื่อ + ราคา + วันหมด + คะแนน + แท็ก + ลิงก์
- **Status Embed:** แพลตฟอร์มไหนมีแจก (✅/❌)

##  GitHub Actions Setup

1. **Add Secret:**
   - Settings → Secrets → New secret
   - Name: `DISCORD_WEBHOOK_URL`
   - Value: Your webhook URL

2. **Workflow File:** `.github/workflows/notify.yml`
  - ตั้งค่าแล้ว (รันทุกวัน 22:01 น. เวลาไทย)
   - เก็บ `notified.json` ใน Git

##  สถานะไฟล์

```
notified.json  - เกมที่เคยแจ้งแล้ว (ไม่แจ้งซ้ำ)
status.json    - สถานะแพลตฟอร์ม (เพื่อตรวจหาการเปลี่ยนแปลง)
```

##  Troubleshooting

### "Error: DISCORD_WEBHOOK_URL environment variable is not set"
```bash
# ลืมตั้งค่า env var?
$env:DISCORD_WEBHOOK_URL = "https://discord.com/api/webhooks/..."
```

### "ไม่ได้ส่งแจ้งเตือน"
```bash
# เกมอยู่ใน notified.json แล้ว? (Dedup ทำงาน)
DEBUG=1 python3 notify.py  # ดู debug logs
```

### "ลบ notified.json เพื่อรีเซต"
```bash
rm notified.json
python3 notify.py  # จะตรวจสอบและแจ้งใหม่
```

##  Log Output

```
เริ่ม bot แจ้งเตือนเกมฟรี (polling)...
[2026-06-19T02:24:29.280572] ตรวจสอบเกมฟรี...
พบ Epic: 0 เกม, Steam: 1 เกม
ส่งแจ้งเตือนเกมใหม่: 1
ส่งสำเร็จ batch 1 (1 เกม)
รันแบบครั้งเดียวเสร็จสิ้น
```

##  Debug Mode

```bash
DEBUG=1 python3 notify.py
```

Output:
```
[EPIC SKIP] not free offer for RollerCoaster Tycoon
[EPIC SKIP] no promotions for Them's Fightin' Herds
[STEAM Fallback] accepting based on search for appid 1180660
```

##  API References

- **Epic Games:** https://store-site-backend-static.ak.epicgames.com/freeGamesPromotions
- **Steam:** https://store.steampowered.com/search/results/?maxprice=free&specials=1&json=1

##  License

MIT License

##  Contributing

Pull requests welcome!

---

**Created:** 2026-06-19  
**Language:** Python 3.7+  
**Status:** ✅ Production Ready