# -*- coding: utf-8 -*-
import sys, datetime as dt
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QFont, QIcon, QPixmap, QColor, QAction
from PySide6.QtWidgets import (
    QApplication, QWidget, QMainWindow, QHBoxLayout, QVBoxLayout, QLabel,
    QPushButton, QStackedWidget, QListWidget, QListWidgetItem, QTableWidget,
    QTableWidgetItem, QCheckBox, QTimeEdit, QComboBox, QLineEdit, QSpinBox,
    QFileDialog, QMessageBox, QHeaderView, QSystemTrayIcon, QMenu, QTextEdit
)
import engine as E

QSS = """
QWidget{background:#0f1420;color:#e8edf7;font-family:'Sarabun','Tahoma';font-size:14px}
#side{background:#161d2e;border-right:1px solid #2b3550}
#side QListWidget{background:transparent;border:none;font-size:15px}
#side QListWidget::item{padding:12px 16px;margin:2px 8px;border-radius:9px;color:#8c99b5}
#side QListWidget::item:selected{background:#4da3ff26;color:#4da3ff;font-weight:bold}
#card{background:#1c2438;border:1px solid #2b3550;border-radius:14px}
#clockbox{background:#151b2b;border:1px solid #2b3550;border-radius:18px}
#bigclock{color:#ffffff;font-family:'Consolas';font-size:88px;font-weight:bold}
QPushButton{background:#4da3ff;color:#08101f;border:none;border-radius:9px;
            padding:9px 16px;font-weight:bold}
QPushButton:hover{background:#6fb6ff}
QPushButton#ghost{background:transparent;border:1px solid #2b3550;color:#e8edf7}
QPushButton#danger{background:#ff5c6c1f;border:1px solid #ff5c6c40;color:#ff5c6c}
QLineEdit,QComboBox,QTimeEdit,QSpinBox,QTextEdit{background:#121828;border:1px solid #2b3550;
            border-radius:8px;padding:8px}
QTableWidget{background:#1c2438;gridline-color:#2b3550;border:none}
QHeaderView::section{background:#161d2e;color:#8c99b5;border:none;padding:8px}
QCheckBox{spacing:8px}
QLabel#h1{font-size:22px;font-weight:bold}
QLabel#dim{color:#8c99b5;font-size:12px}
"""

DAYS = ["จ", "อ", "พ", "พฤ", "ศ", "ส", "อา"]
TH_MONTH = ["มกราคม","กุมภาพันธ์","มีนาคม","เมษายน","พฤษภาคม","มิถุนายน","กรกฎาคม",
            "สิงหาคม","กันยายน","ตุลาคม","พฤศจิกายน","ธันวาคม"]
TH_WDAY = ["จันทร์","อังคาร","พุธ","พฤหัสบดี","ศุกร์","เสาร์","อาทิตย์"]


def card(*widgets):
    w = QWidget(); w.setObjectName("card")
    lay = QVBoxLayout(w); lay.setContentsMargins(18, 16, 18, 16); lay.setSpacing(10)
    for x in widgets:
        lay.addWidget(x) if isinstance(x, QWidget) else lay.addLayout(x)
    return w


class Main(QMainWindow):
    def __init__(self):
        super().__init__()
        self.cfg = E.load()
        self.clock = E.ThaiClock(self.cfg["ntp_server"])
        self.player = E.Player()
        self.speaker = E.Speaker()
        self.sched = E.Scheduler(self.cfg, self.clock, self.player, self.speaker)

        self.setWindowTitle("นาฬิกาโรงเรียน — School Clock")
        self.resize(1180, 760)

        root = QWidget(); self.setCentralWidget(root)
        lay = QHBoxLayout(root); lay.setContentsMargins(0, 0, 0, 0); lay.setSpacing(0)

        side = QWidget(); side.setObjectName("side"); side.setFixedWidth(220)
        sl = QVBoxLayout(side)
        title = QLabel("🔔  นาฬิกาโรงเรียน"); title.setStyleSheet("font-size:16px;font-weight:bold;padding:10px")
        self.menu = QListWidget()
        for t in ["🕐  หน้าหลัก", "🗣️  เสียงบอกเวลา", "🎵  ตารางเสียง",
                  "▶️  YouTube", "⏻  เปิด–ปิดเครื่อง", "⚙️  ตั้งค่า", "📋  ประวัติ"]:
            self.menu.addItem(QListWidgetItem(t))
        self.menu.setCurrentRow(0)
        self.lbl_sync = QLabel("กำลังซิงก์เวลา…"); self.lbl_sync.setObjectName("dim")
        self.lbl_sync.setWordWrap(True)
        sl.addWidget(title); sl.addWidget(self.menu); sl.addStretch(); sl.addWidget(self.lbl_sync)

        self.stack = QStackedWidget()
        self.stack.addWidget(self.page_home())
        self.stack.addWidget(self.page_speak())
        self.stack.addWidget(self.page_tasks("sound"))
        self.stack.addWidget(self.page_tasks("youtube"))
        self.stack.addWidget(self.page_power())
        self.stack.addWidget(self.page_settings())
        self.stack.addWidget(self.page_log())
        self.menu.currentRowChanged.connect(self.stack.setCurrentIndex)

        lay.addWidget(side); lay.addWidget(self.stack, 1)

        self.tray_setup()
        self.clock.sync_async()
        self.t = QTimer(self); self.t.timeout.connect(self.tick); self.t.start(250)
        self.tsync = QTimer(self); self.tsync.timeout.connect(self.clock.sync_async)
        self.tsync.start(self.cfg["sync_every_min"] * 60000)

    # ---------- หน้า 1 ----------
    def page_home(self):
        p = QWidget(); v = QVBoxLayout(p); v.setContentsMargins(24, 22, 24, 22)
        h = QLabel("หน้าหลัก"); h.setObjectName("h1")

        box = QWidget(); box.setObjectName("clockbox")
        bv = QVBoxLayout(box); bv.setContentsMargins(20, 26, 20, 26)
        self.lbl_clock = QLabel("--:--:--"); self.lbl_clock.setObjectName("bigclock")
        self.lbl_clock.setAlignment(Qt.AlignCenter)
        self.lbl_date = QLabel(""); self.lbl_date.setAlignment(Qt.AlignCenter)
        self.lbl_date.setStyleSheet("font-size:18px")
        bv.addWidget(self.lbl_clock); bv.addWidget(self.lbl_date)

        row = QHBoxLayout()
        b1 = QPushButton("🔄 ซิงก์เวลาเดี๋ยวนี้"); b1.clicked.connect(self.clock.sync_async)
        b2 = QPushButton("⏹ หยุดเสียงทันที"); b2.setObjectName("danger")
        b2.clicked.connect(self.player.stop)
        b3 = QPushButton("✖ ยกเลิกการปิดเครื่อง"); b3.setObjectName("ghost")
        b3.clicked.connect(E.cancel_power)
        row.addWidget(b1); row.addWidget(b2); row.addWidget(b3); row.addStretch()

        self.chk_silent = QCheckBox("โหมดเงียบ — ปิดเสียงทั้งหมดชั่วคราว (ใช้ช่วงสอบ)")
        self.chk_silent.setChecked(self.cfg["silent_mode"])
        self.chk_silent.toggled.connect(lambda b: self.cfg.update(silent_mode=b))

        self.lbl_next = QLabel("—"); self.lbl_next.setWordWrap(True)
        v.addWidget(h); v.addWidget(box); v.addLayout(row)
        v.addWidget(card(QLabel("⏭️ คิวงานถัดไป"), self.lbl_next, self.chk_silent))
        v.addStretch()
        return p

    # ---------- หน้า 2 ----------
    def page_speak(self):
        s = self.cfg["speak"]
        p = QWidget(); v = QVBoxLayout(p); v.setContentsMargins(24, 22, 24, 22)
        h = QLabel("เสียงบอกเวลา"); h.setObjectName("h1")
        self.sp_on = QCheckBox("เปิดใช้งานเสียงบอกเวลา"); self.sp_on.setChecked(s["enabled"])
        self.sp_mode = QComboBox(); self.sp_mode.addItems(["ทุกชั่วโมงเต็ม", "ทุก 30 นาที", "ทุก 15 นาที"])
        self.sp_mode.setCurrentIndex({"hour": 0, "half": 1, "quarter": 2}[s["mode"]])
        self.sp_start = QTimeEdit(); self.sp_start.setDisplayFormat("HH:mm")
        self.sp_start.setTime(dt.datetime.strptime(s["start"], "%H:%M").time())
        self.sp_end = QTimeEdit(); self.sp_end.setDisplayFormat("HH:mm")
        self.sp_end.setTime(dt.datetime.strptime(s["end"], "%H:%M").time())
        self.sp_prefix = QLineEdit(s["prefix"]); self.sp_suffix = QLineEdit(s["suffix"])
        self.sp_days = [QCheckBox(d) for d in DAYS]
        for i, c in enumerate(self.sp_days):
            c.setChecked(i in s["days"])
        drow = QHBoxLayout()
        for c in self.sp_days:
            drow.addWidget(c)
        drow.addStretch()

        test = QPushButton("🔊 ทดลองฟัง")
        test.clicked.connect(lambda: self.speaker.say(E.time_phrase(self.clock.now(), self.cfg)))
        sv = QPushButton("💾 บันทึก"); sv.clicked.connect(self.save_speak)

        v.addWidget(h)
        v.addWidget(card(self.sp_on, QLabel("รอบการบอกเวลา"), self.sp_mode,
                         QLabel("ตั้งแต่เวลา"), self.sp_start, QLabel("ถึงเวลา"), self.sp_end,
                         QLabel("วันที่ทำงาน"), drow,
                         QLabel("ข้อความนำหน้า"), self.sp_prefix,
                         QLabel("ข้อความต่อท้าย"), self.sp_suffix))
        r = QHBoxLayout(); r.addWidget(test); r.addWidget(sv); r.addStretch()
        v.addLayout(r); v.addStretch()
        return p

    def save_speak(self):
        s = self.cfg["speak"]
        s["enabled"] = self.sp_on.isChecked()
        s["mode"] = ["hour", "half", "quarter"][self.sp_mode.currentIndex()]
        s["start"] = self.sp_start.time().toString("HH:mm")
        s["end"] = self.sp_end.time().toString("HH:mm")
        s["prefix"] = self.sp_prefix.text(); s["suffix"] = self.sp_suffix.text()
        s["days"] = [i for i, c in enumerate(self.sp_days) if c.isChecked()]
        E.save(self.cfg); self.toast("บันทึกแล้ว")

    # ---------- หน้า 3 & 4 ----------
    def page_tasks(self, kind):
        p = QWidget(); v = QVBoxLayout(p); v.setContentsMargins(24, 22, 24, 22)
        h = QLabel("ตารางเล่นไฟล์เสียง" if kind == "sound" else "เปิดลิงก์ YouTube ตามเวลา")
        h.setObjectName("h1")
        tb = QTableWidget(0, 6)
        tb.setHorizontalHeaderLabels(
            ["เวลา", "ชื่อรายการ", "ไฟล์เสียง" if kind == "sound" else "ลิงก์",
             "วันทำงาน", "เล่นนาน(นาที)", "เปิดใช้"])
        tb.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        tb.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        setattr(self, f"tb_{kind}", tb)
        self.reload_table(kind)

        time_e = QTimeEdit(); time_e.setDisplayFormat("HH:mm")
        name_e = QLineEdit(); name_e.setPlaceholderText("ชื่อรายการ")
        path_e = QLineEdit(); path_e.setPlaceholderText(
            "เลือกไฟล์เสียง…" if kind == "sound" else "https://youtu.be/xxxx")
        dur_e = QSpinBox(); dur_e.setRange(0, 600); dur_e.setSuffix(" นาที (0 = จนจบ)")
        days = [QCheckBox(d) for d in DAYS]
        for i in range(5):
            days[i].setChecked(True)

        r1 = QHBoxLayout(); r1.addWidget(time_e); r1.addWidget(name_e, 2); r1.addWidget(path_e, 3)
        if kind == "sound":
            br = QPushButton("เลือกไฟล์"); br.setObjectName("ghost")
            br.clicked.connect(lambda: path_e.setText(
                QFileDialog.getOpenFileName(self, "เลือกไฟล์เสียง", "",
                                            "Audio (*.mp3 *.wav *.m4a)")[0]))
            r1.addWidget(br)
        r2 = QHBoxLayout()
        for c in days:
            r2.addWidget(c)
        r2.addWidget(dur_e); r2.addStretch()
        add = QPushButton("＋ เพิ่มรายการ")
        dele = QPushButton("🗑 ลบที่เลือก"); dele.setObjectName("danger")
        test = QPushButton("▶ ทดลองเล่น"); test.setObjectName("ghost")
        r3 = QHBoxLayout(); r3.addWidget(add); r3.addWidget(test); r3.addWidget(dele); r3.addStretch()

        def add_task():
            if not path_e.text():
                return
            self.cfg["tasks"].append({
                "type": kind, "time": time_e.time().toString("HH:mm"),
                "name": name_e.text() or "ไม่มีชื่อ",
                ("file" if kind == "sound" else "url"): path_e.text(),
                "days": [i for i, c in enumerate(days) if c.isChecked()],
                "duration": dur_e.value() * (60 if kind == "sound" else 1),
                "volume": 95, "enabled": True})
            E.save(self.cfg); self.reload_table(kind)
            name_e.clear(); path_e.clear()

        def del_task():
            rows = sorted({i.row() for i in tb.selectedIndexes()}, reverse=True)
            idx = [i for i, t in enumerate(self.cfg["tasks"]) if t["type"] == kind]
            for r in rows:
                if r < len(idx):
                    self.cfg["tasks"].pop(idx[r])
            E.save(self.cfg); self.reload_table(kind)

        def test_play():
            if kind == "sound":
                self.player.play(path_e.text(), 95, 0)
            else:
                E.open_youtube(path_e.text(), 0)

        add.clicked.connect(add_task); dele.clicked.connect(del_task); test.clicked.connect(test_play)
        v.addWidget(h); v.addWidget(tb, 1)
        v.addWidget(card(QLabel("เพิ่มรายการใหม่"), r1, r2, r3))
        return p

    def reload_table(self, kind):
        tb = getattr(self, f"tb_{kind}", None)
        if tb is None:
            return
        rows = [t for t in self.cfg["tasks"] if t["type"] == kind]
        tb.setRowCount(len(rows))
        for r, t in enumerate(rows):
            vals = [t["time"], t["name"], t.get("file") or t.get("url", ""),
                    " ".join(DAYS[d] for d in t["days"]),
                    str(t.get("duration", 0)), "เปิด" if t.get("enabled") else "ปิด"]
            for c, val in enumerate(vals):
                tb.setItem(r, c, QTableWidgetItem(val))

    # ---------- หน้า 5 ----------
    def page_power(self):
        sd, wk = self.cfg["shutdown"], self.cfg["wake"]
        p = QWidget(); v = QVBoxLayout(p); v.setContentsMargins(24, 22, 24, 22)
        h = QLabel("เปิด–ปิดคอมพิวเตอร์อัตโนมัติ"); h.setObjectName("h1")

        self.sd_on = QCheckBox("เปิดใช้งานการปิดเครื่องอัตโนมัติ"); self.sd_on.setChecked(sd["enabled"])
        self.sd_time = QTimeEdit(); self.sd_time.setDisplayFormat("HH:mm")
        self.sd_time.setTime(dt.datetime.strptime(sd["time"], "%H:%M").time())
        self.sd_act = QComboBox(); self.sd_act.addItems(["shutdown", "restart", "hibernate", "logoff"])
        self.sd_warn = QSpinBox(); self.sd_warn.setRange(0, 600); self.sd_warn.setValue(sd["warn_sec"])
        self.sd_warn.setSuffix(" วินาที (เตือนล่วงหน้า)")
        self.sd_days = [QCheckBox(d) for d in DAYS]
        for i, c in enumerate(self.sd_days):
            c.setChecked(i in sd["days"])
        dr = QHBoxLayout()
        for c in self.sd_days:
            dr.addWidget(c)
        dr.addStretch()

        self.wk_on = QCheckBox("เปิดใช้งานการปลุกเครื่องอัตโนมัติ"); self.wk_on.setChecked(wk["enabled"])
        self.wk_time = QTimeEdit(); self.wk_time.setDisplayFormat("HH:mm")
        self.wk_time.setTime(dt.datetime.strptime(wk["time"], "%H:%M").time())
        note = QLabel("ℹ️ การปลุกเครื่องทำได้เฉพาะตอนเครื่องอยู่ในสถานะ Sleep / Hibernate\n"
                      "ถ้าสั่ง Shutdown เต็มรูปแบบ ต้องเปิด RTC Alarm ในไบออส และปิด Fast Startup")
        note.setStyleSheet("color:#ffd58a;background:#ffb0201a;border-radius:8px;padding:10px")
        note.setWordWrap(True)

        sv = QPushButton("💾 บันทึก"); sv.clicked.connect(self.save_power)
        v.addWidget(h)
        v.addWidget(card(self.sd_on, QLabel("เวลาปิดเครื่อง"), self.sd_time,
                         QLabel("การกระทำ"), self.sd_act, self.sd_warn,
                         QLabel("วันที่ทำงาน"), dr))
        v.addWidget(card(self.wk_on, QLabel("เวลาเปิดเครื่อง"), self.wk_time, note))
        v.addWidget(sv); v.addStretch()
        return p

    def save_power(self):
        sd, wk = self.cfg["shutdown"], self.cfg["wake"]
        sd["enabled"] = self.sd_on.isChecked()
        sd["time"] = self.sd_time.time().toString("HH:mm")
        sd["action"] = self.sd_act.currentText()
        sd["warn_sec"] = self.sd_warn.value()
        sd["days"] = [i for i, c in enumerate(self.sd_days) if c.isChecked()]
        wk["enabled"] = self.wk_on.isChecked()
        wk["time"] = self.wk_time.time().toString("HH:mm")
        E.save(self.cfg)
        ok, msg = E.set_wake_task(wk["enabled"], wk["time"])
        self.toast(msg if wk["enabled"] else "บันทึกแล้ว")

    # ---------- หน้า 6 ----------
    def page_settings(self):
        p = QWidget(); v = QVBoxLayout(p); v.setContentsMargins(24, 22, 24, 22)
        h = QLabel("ตั้งค่าระบบ"); h.setObjectName("h1")
        self.st_startup = QCheckBox("เริ่มโปรแกรมอัตโนมัติเมื่อเปิดเครื่อง (Startup)")
        self.st_startup.setChecked(self.cfg["startup"])
        self.st_startup.toggled.connect(self.toggle_startup)
        self.st_ntp = QComboBox()
        self.st_ntp.addItems(["time.navy.mi.th", "time1.nimt.or.th",
                              "clock.nectec.or.th", "pool.ntp.org"])
        self.st_ntp.setCurrentText(self.cfg["ntp_server"])
        self.st_every = QSpinBox(); self.st_every.setRange(5, 1440)
        self.st_every.setValue(self.cfg["sync_every_min"]); self.st_every.setSuffix(" นาที/ครั้ง")
        path = QLabel(f"ตำแหน่งโปรแกรม: {E.base_dir()}"); path.setObjectName("dim")
        path.setWordWrap(True)
        sv = QPushButton("💾 บันทึก"); sv.clicked.connect(self.save_settings)
        v.addWidget(h)
        v.addWidget(card(self.st_startup, QLabel("แหล่งเวลามาตรฐานไทย"), self.st_ntp,
                         QLabel("ความถี่ในการซิงก์"), self.st_every, path))
        v.addWidget(sv); v.addStretch()
        return p

    def toggle_startup(self, b):
        try:
            E.set_startup(b); self.cfg["startup"] = b; E.save(self.cfg)
        except Exception as e:
            QMessageBox.warning(self, "ผิดพลาด", str(e))

    def save_settings(self):
        self.cfg["ntp_server"] = self.st_ntp.currentText()
        self.cfg["sync_every_min"] = self.st_every.value()
        self.clock.server = self.cfg["ntp_server"]
        self.tsync.start(self.cfg["sync_every_min"] * 60000)
        E.save(self.cfg); self.clock.sync_async(); self.toast("บันทึกแล้ว")

    # ---------- หน้า 7 ----------
    def page_log(self):
        p = QWidget(); v = QVBoxLayout(p); v.setContentsMargins(24, 22, 24, 22)
        h = QLabel("ประวัติการทำงาน"); h.setObjectName("h1")
        self.logbox = QTextEdit(); self.logbox.setReadOnly(True)
        rl = QPushButton("🔄 รีเฟรช"); rl.clicked.connect(self.refresh_log)
        v.addWidget(h); v.addWidget(rl); v.addWidget(self.logbox, 1)
        self.refresh_log()
        return p

    def refresh_log(self):
        try:
            with open(E.LOGFILE, encoding="utf-8") as f:
                lines = f.readlines()[-300:]
            self.logbox.setPlainText("".join(reversed(lines)))
        except Exception:
            self.logbox.setPlainText("ยังไม่มีบันทึก")

    # ---------- ระบบ ----------
    def tray_setup(self):
        pm = QPixmap(64, 64); pm.fill(QColor("#4da3ff"))
        self.tray = QSystemTrayIcon(QIcon(pm), self)
        m = QMenu()
        a1 = QAction("แสดงหน้าต่าง", self); a1.triggered.connect(self.showNormal)
        a2 = QAction("หยุดเสียง", self); a2.triggered.connect(self.player.stop)
        a3 = QAction("ออกจากโปรแกรม", self); a3.triggered.connect(QApplication.quit)
        m.addAction(a1); m.addAction(a2); m.addSeparator(); m.addAction(a3)
        self.tray.setContextMenu(m)
        self.tray.setToolTip("นาฬิกาโรงเรียน")
        self.tray.activated.connect(lambda r: self.showNormal() if r == QSystemTrayIcon.Trigger else None)
        self.tray.show()

    def toast(self, msg):
        self.tray.showMessage("นาฬิกาโรงเรียน", msg, QSystemTrayIcon.Information, 2500)

    def tick(self):
        now = self.clock.now()
        self.lbl_clock.setText(now.strftime("%H:%M:%S"))
        self.lbl_date.setText(
            f"วัน{TH_WDAY[now.weekday()]}ที่ {now.day} {TH_MONTH[now.month-1]} พ.ศ. {now.year+543}")
        st = "🌐 ออนไลน์" if self.clock.online else "⚠️ ออฟไลน์ (ใช้นาฬิกาเครื่อง)"
        ls = self.clock.last_sync.strftime("%H:%M:%S") if self.clock.last_sync else "-"
        self.lbl_sync.setText(f"{st}\nซิงก์ล่าสุด {ls}\nคลาด {self.clock.offset:+.3f} วิ")
        self.sched.tick()
        self.update_next(now)

    def update_next(self, now):
        items = []
        for t in self.cfg["tasks"]:
            if not t.get("enabled", True):
                continue
            hh, mm = map(int, t["time"].split(":"))
            tgt = now.replace(hour=hh, minute=mm, second=0, microsecond=0)
            if tgt < now:
                continue
            items.append((tgt, t["name"], t["type"]))
        items.sort()
        if not items:
            self.lbl_next.setText("ไม่มีรายการที่รออยู่ในวันนี้")
            return
        txt = []
        for tgt, name, kind in items[:5]:
            left = int((tgt - now).total_seconds() // 60)
            icon = {"sound": "🎵", "youtube": "▶️", "speak": "🗣️"}.get(kind, "•")
            txt.append(f"{tgt:%H:%M}   {icon} {name}   — อีก {left} นาที")
        self.lbl_next.setText("\n".join(txt))

    def closeEvent(self, e):
        e.ignore(); self.hide()
        self.toast("โปรแกรมยังทำงานอยู่ในถาดระบบ")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    app.setStyleSheet(QSS)
    w = Main(); w.show()
    sys.exit(app.exec())
