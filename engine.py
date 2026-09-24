# -*- coding: utf-8 -*-
"""แกนระบบนาฬิกาโรงเรียน: ซิงก์เวลาไทย, ตัวจับตาราง, เล่นเสียง, พาวเวอร์, startup"""
import os, sys, json, threading, subprocess, webbrowser, datetime as dt

APP_NAME = "SchoolClock"

# ---------- ที่เก็บไฟล์ (แบบพกพา: อยู่ข้าง .exe) ----------
def base_dir():
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))

SETTINGS = os.path.join(base_dir(), "settings.json")
LOGFILE  = os.path.join(base_dir(), "schoolclock.log")
SOUNDDIR = os.path.join(base_dir(), "sounds")

DEFAULT = {
    "ntp_server": "time.navy.mi.th",
    "sync_every_min": 60,
    "master_volume": 85,
    "silent_mode": False,
    "startup": False,
    "speak": {
        "enabled": True, "mode": "hour",          # hour | half | quarter
        "start": "07:00", "end": "17:00",
        "days": [0, 1, 2, 3, 4],                  # 0=จันทร์
        "prefix": "ขณะนี้เวลา", "suffix": "นาฬิกา",
        "volume": 90
    },
    "tasks": [
        # {"type":"sound","time":"07:55","name":"ออดเข้าแถว","file":"bell.wav",
        #  "days":[0,1,2,3,4],"duration":0,"volume":95,"enabled":True}
        # {"type":"youtube","time":"12:00","name":"เพลงพักเที่ยง",
        #  "url":"https://youtu.be/xxxx","days":[0,1,2,3,4],"duration":45,"enabled":True}
    ],
    "shutdown": {"enabled": False, "time": "17:30", "days": [0,1,2,3,4],
                 "action": "shutdown", "warn_sec": 60},
    "wake": {"enabled": False, "time": "06:45", "days": [0,1,2,3,4]},
}


def load():
    if os.path.exists(SETTINGS):
        try:
            with open(SETTINGS, encoding="utf-8") as f:
                d = json.load(f)
            merged = json.loads(json.dumps(DEFAULT))
            merged.update(d)
            return merged
        except Exception:
            pass
    return json.loads(json.dumps(DEFAULT))


def save(cfg):
    with open(SETTINGS, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)


def log(msg, level="ok"):
    line = f"[{dt.datetime.now():%d/%m/%Y %H:%M:%S}] [{level}] {msg}\n"
    try:
        with open(LOGFILE, "a", encoding="utf-8") as f:
            f.write(line)
    except Exception:
        pass
    return line


# ---------- 1) เวลาไทยออนไลน์ (ไม่แก้นาฬิกาเครื่อง ใช้ offset) ----------
class ThaiClock:
    """เก็บค่าชดเชยจาก NTP แล้วบวกกับนาฬิกาเครื่อง จึงไม่ต้องใช้สิทธิ์ Admin"""
    def __init__(self, server="time.navy.mi.th"):
        self.server = server
        self.offset = 0.0
        self.online = False
        self.last_sync = None

    def sync(self):
        try:
            import ntplib
            r = ntplib.NTPClient().request(self.server, version=3, timeout=5)
            self.offset = r.offset
            self.online = True
            self.last_sync = dt.datetime.now()
            log(f"ซิงก์เวลาจาก {self.server} สำเร็จ (offset {self.offset:+.3f}s)")
        except Exception as e:
            self.online = False
            log(f"ซิงก์เวลาไม่สำเร็จ: {e} — ใช้นาฬิกาเครื่องชั่วคราว", "error")
        return self.online

    def sync_async(self):
        threading.Thread(target=self.sync, daemon=True).start()

    def now(self):
        return dt.datetime.now() + dt.timedelta(seconds=self.offset)


# ---------- 2) เสียงพูดบอกเวลา (TTS ไทย) ----------
class Speaker:
    def __init__(self):
        self._lock = threading.Lock()

    def say(self, text, volume=90):
        threading.Thread(target=self._run, args=(text, volume), daemon=True).start()

    def _run(self, text, volume):
        with self._lock:
            try:
                import pyttsx3
                eng = pyttsx3.init()
                eng.setProperty("volume", volume / 100.0)
                for v in eng.getProperty("voices"):
                    if "th" in (getattr(v, "id", "") + getattr(v, "name", "")).lower():
                        eng.setProperty("voice", v.id)
                        break
                eng.say(text)
                eng.runAndWait()
                eng.stop()
                log(f'เสียงพูด: "{text}"')
            except Exception as e:
                log(f"พูดไม่สำเร็จ: {e}", "error")


THAI_NUM = ["ศูนย์","หนึ่ง","สอง","สาม","สี่","ห้า","หก","เจ็ด","แปด","เก้า","สิบ",
            "สิบเอ็ด","สิบสอง","สิบสาม","สิบสี่","สิบห้า","สิบหก","สิบเจ็ด","สิบแปด",
            "สิบเก้า","ยี่สิบ","ยี่สิบเอ็ด","ยี่สิบสอง","ยี่สิบสาม"]

def thai_minute(m):
    if m == 0:
        return ""
    if m <= 23:
        return THAI_NUM[m] + "นาที"
    tens = ["", "", "ยี่สิบ", "สามสิบ", "สี่สิบ", "ห้าสิบ"]
    unit = ["", "เอ็ด", "สอง", "สาม", "สี่", "ห้า", "หก", "เจ็ด", "แปด", "เก้า"]
    return tens[m // 10] + unit[m % 10] + "นาที"

def time_phrase(now, cfg):
    s = cfg["speak"]
    h, m = now.hour, now.minute
    return f'{s["prefix"]} {THAI_NUM[h]}{s["suffix"]} {thai_minute(m)}'.strip()


# ---------- 3) เล่นไฟล์เสียง ----------
class Player:
    def __init__(self):
        from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput
        self.out = QAudioOutput()
        self.mp = QMediaPlayer()
        self.mp.setAudioOutput(self.out)

    def play(self, path, volume=95, duration_sec=0):
        from PySide6.QtCore import QUrl, QTimer
        if not os.path.isabs(path):
            path = os.path.join(SOUNDDIR, path)
        if not os.path.exists(path):
            log(f"ไม่พบไฟล์เสียง: {path}", "error")
            return
        self.out.setVolume(volume / 100.0)
        self.mp.setSource(QUrl.fromLocalFile(path))
        self.mp.play()
        log(f"เล่นไฟล์เสียง {os.path.basename(path)}")
        if duration_sec:
            QTimer.singleShot(int(duration_sec * 1000), self.stop)

    def stop(self):
        self.mp.stop()


# ---------- 4) YouTube ----------
def open_youtube(url, duration_min=0):
    u = url
    if "autoplay" not in u:
        u += ("&" if "?" in u else "?") + "autoplay=1"
    webbrowser.open(u)
    log(f"เปิด YouTube: {url}")
    if duration_min:
        def kill():
            for exe in ("chrome.exe", "msedge.exe"):
                subprocess.run(["taskkill", "/IM", exe, "/F"],
                               capture_output=True, shell=True)
            log("ปิดหน้าต่างเบราว์เซอร์เมื่อครบเวลา")
        threading.Timer(duration_min * 60, kill).start()


# ---------- 5) ปิดเครื่อง / ปลุกเครื่อง ----------
def do_power(action="shutdown", delay_sec=60):
    flag = {"shutdown": "/s", "restart": "/r", "logoff": "/l",
            "hibernate": "/h", "sleep": "/h"}.get(action, "/s")
    cmd = ["shutdown", flag, "/t", str(delay_sec)] if flag not in ("/l", "/h") else ["shutdown", flag]
    subprocess.Popen(cmd, shell=True)
    log(f"สั่ง {action} ในอีก {delay_sec} วินาที")

def cancel_power():
    subprocess.run(["shutdown", "/a"], capture_output=True, shell=True)
    log("ยกเลิกการปิดเครื่อง")

def set_wake_task(enabled, hhmm="06:45"):
    """ใช้ Task Scheduler ปลุกเครื่อง (ต้องเป็นสถานะ Sleep/Hibernate)"""
    name = "SchoolClockWake"
    if not enabled:
        subprocess.run(["schtasks", "/Delete", "/TN", name, "/F"],
                       capture_output=True, shell=True)
        return True, "ปิดการปลุกเครื่องแล้ว"
    r = subprocess.run(
        ["schtasks", "/Create", "/TN", name, "/TR", "cmd /c exit",
         "/SC", "DAILY", "/ST", hhmm, "/F"], capture_output=True, shell=True)
    ok = r.returncode == 0
    msg = ("สร้างงานปลุกเครื่องแล้ว — ต้องเข้า Task Scheduler ติ๊ก "
           "'Wake the computer to run this task' อีกครั้งหนึ่ง")
    log(msg if ok else "สร้างงานปลุกเครื่องไม่สำเร็จ (ลองเปิดโปรแกรมแบบ Run as administrator)",
        "ok" if ok else "error")
    return ok, msg


# ---------- 6) Startup ----------
def set_startup(enabled):
    import winreg
    key = winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                         r"Software\Microsoft\Windows\CurrentVersion\Run", 0,
                         winreg.KEY_SET_VALUE)
    exe = sys.executable if getattr(sys, "frozen", False) else sys.argv[0]
    try:
        if enabled:
            winreg.SetValueEx(key, APP_NAME, 0, winreg.REG_SZ, f'"{exe}"')
        else:
            try:
                winreg.DeleteValue(key, APP_NAME)
            except FileNotFoundError:
                pass
    finally:
        winreg.CloseKey(key)
    log(f"ตั้งค่าเริ่มอัตโนมัติ: {'เปิด' if enabled else 'ปิด'}")


# ---------- 7) ตัวจับตาราง ----------
class Scheduler:
    """เช็คทุกวินาที ยิงงานเมื่อ HH:MM:00 ตรงและยังไม่เคยยิงในนาทีนั้น"""
    def __init__(self, cfg, clock, player, speaker):
        self.cfg, self.clock = cfg, clock
        self.player, self.speaker = player, speaker
        self.fired = set()

    def _key(self, now, tag):
        return f"{now:%Y%m%d%H%M}-{tag}"

    def tick(self):
        cfg, now = self.cfg, self.clock.now()
        wd = now.weekday()
        if now.second != 0:
            return
        if cfg.get("silent_mode"):
            return

        # เสียงบอกเวลา
        s = cfg["speak"]
        if s["enabled"] and wd in s["days"]:
            sh, sm = map(int, s["start"].split(":"))
            eh, em = map(int, s["end"].split(":"))
            in_range = (sh * 60 + sm) <= (now.hour * 60 + now.minute) <= (eh * 60 + em)
            step = {"hour": 60, "half": 30, "quarter": 15}.get(s["mode"], 60)
            if in_range and now.minute % step == 0:
                k = self._key(now, "speak")
                if k not in self.fired:
                    self.fired.add(k)
                    self.speaker.say(time_phrase(now, cfg), s["volume"])

        # งานในตาราง
        for i, t in enumerate(cfg["tasks"]):
            if not t.get("enabled", True) or wd not in t.get("days", []):
                continue
            if t["time"] != f"{now:%H:%M}":
                continue
            k = self._key(now, f"task{i}")
            if k in self.fired:
                continue
            self.fired.add(k)
            if t["type"] == "sound":
                self.player.play(t["file"], t.get("volume", 95), t.get("duration", 0))
            elif t["type"] == "youtube":
                open_youtube(t["url"], t.get("duration", 0))
            elif t["type"] == "speak":
                self.speaker.say(t.get("text", ""), t.get("volume", 90))

        # ปิดเครื่อง
        sd = cfg["shutdown"]
        if sd["enabled"] and wd in sd["days"] and sd["time"] == f"{now:%H:%M}":
            k = self._key(now, "power")
            if k not in self.fired:
                self.fired.add(k)
                self.speaker.say(f'ระบบจะปิดเครื่องในอีก {sd["warn_sec"]} วินาที')
                do_power(sd["action"], sd["warn_sec"])

        if len(self.fired) > 500:
            self.fired.clear()
