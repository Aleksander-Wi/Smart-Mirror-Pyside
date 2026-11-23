from pathlib import Path
import sys
from PySide6.QtCore import QTimer, Qt
from PySide6.QtGui import QFontDatabase, QPainter, QPixmap

from PySide6.QtWidgets import QApplication, QHBoxLayout, QLabel, QVBoxLayout, QWidget

from zoneinfo import ZoneInfo
from astral import LocationInfo
from astral.sun import sun

from datetime import datetime, timedelta


BASE_DIR = Path(__file__).parent
ICONS_DIR = BASE_DIR / "icons"
PICTURES_DIR = BASE_DIR / "pictures"

# for sun/moon icon
TZ = ZoneInfo("Europe/Warsaw")
LOCATION = LocationInfo(
    name="Szczecin",
    region="Poland",
    timezone="Europe/Warsaw",
    latitude=53.4285,
    longitude=14.5528,
)

# Clock_Icon
CENTER = (681, 433)
AXIS_ANGLE = -22
SQUASH = 0.75
SPEED = 100

WATCH_POS = (0.55, 0.48)   # scale pos

# pivot point of each hand within its file (x, y in pixels)
PIVOTS = {
    "hour": (681, 433),
    "min":  (681, 433),
}

PHASE_TO_ICON = {
    "day": "sun",
    "sunset": "sunrise",
    "night": "moon",
}


STYLES = {
    # zegar
    "clock":    {"family": "Monoton",           "size": 120, "color": "#FFFB00"},
    "hours":    {"family": "Protest Guerrilla", "size": 100, "color": "#FF0000"},
    "minutes":  {"family": "Tilt Prism",        "size": 80,  "color": "#00F5FF"},
    "seconds":  {"family": "Redaction 35",      "size": 70,  "color": "#03FF00"},

    # data
    "week_day": {"family": "Protest Guerrilla", "size": 160, "color": "#FFFFFF"},
    "day":      {"family": "Protest Guerrilla", "size": 100, "color": "#FF0000"},
    "month":    {"family": "Protest Guerrilla", "size": 100, "color": "#FF0000"},
    "year":     {"family": "Protest Guerrilla", "size": 100, "color": "#FF0000"},
}

# for sun/moon icon


def get_phase(now: datetime | None = None) -> str:
    current = now.astimezone(TZ) if now else datetime.now(TZ)
    events = sun(LOCATION.observer, date=current.date(), tzinfo=TZ)

    sunrise = events["sunrise"]
    sunset = events["sunset"]
    sunset_margin = timedelta(minutes=30)

    if sunset - sunset_margin <= current <= sunset + sunset_margin:
        return "sunset"
    if sunrise <= current < sunset - sunset_margin:
        return "day"
    return "night"


def style_for(key):
    s = STYLES[key]
    return f"font-size: {s['size']}px; font-family:'{s['family']}'; color: {s['color']};"


class PhaseIconController:

    def __init__(self, icons: dict[str, QPixmap], on_change=None):
        self.icons = icons
        self.on_change = on_change
        self.current_phase: str | None = None
        self.current_pixmap: QPixmap | None = None

    def refresh(self) -> bool:
        phase = get_phase()
        icon_key = PHASE_TO_ICON.get(phase, phase)
        if phase != self.current_phase and icon_key in self.icons:
            self.current_phase = phase
            self.current_pixmap = self.icons[icon_key]
            if self.on_change:
                self.on_change()
            return True
        return False


class PocketWatch(QWidget):
    def __init__(self, face, hour, minute, scale=0.25):
        super().__init__()
        self.scale_f = scale
        self.face = QPixmap(face)
        self.hands = {"hour": QPixmap(hour), "min": QPixmap(minute)}
        self.setFixedSize(int(self.face.width() * scale),
                          int(self.face.height() * scale))
        self.setAttribute(Qt.WA_TranslucentBackground)

        self.t0 = datetime.now()
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update)
        self.timer.start(50)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHints(QPainter.Antialiasing |
                         QPainter.SmoothPixmapTransform)
        p.scale(self.scale_f, self.scale_f)
        p.drawPixmap(0, 0, self.face)

        elapsed = (datetime.now() - self.t0).total_seconds() * SPEED
        minute = (elapsed / 60) % 60
        hour = (elapsed / 3600) % 12

        p.translate(*CENTER)
        p.rotate(AXIS_ANGLE)
        p.scale(1.0, SQUASH)
        self.draw_hand(p, "hour", hour * 30)
        self.draw_hand(p, "min", minute * 6)

    def draw_hand(self, p, name, angle):
        px, py = PIVOTS[name]
        p.save()
        p.rotate(angle)
        p.drawPixmap(-px, -py, self.hands[name])
        p.restore()


def load_fonts():
    families = []
    for path in (BASE_DIR / "fonts").glob("*.ttf"):
        font_id = QFontDatabase.addApplicationFont(str(path))
        if font_id == -1:
            print(f"Failed to load font: {path}")
            continue
        families.extend(QFontDatabase.applicationFontFamilies(font_id))
        print(f"Loaded font: {path} with families: {families}")
    return families


def png_to_pixmap(path: Path, size: int = 256, tint_white: bool = False) -> QPixmap:
    pm = QPixmap(str(path))
    if pm.isNull():
        print(f"Failed to load PNG: {path}")
        return QPixmap()

    pm = pm.scaled(size, size, Qt.KeepAspectRatio, Qt.SmoothTransformation)

    if tint_white:
        tinted = QPixmap(pm.size())
        tinted.fill(Qt.transparent)
        painter = QPainter(tinted)
        painter.drawPixmap(0, 0, pm)
        painter.setCompositionMode(QPainter.CompositionMode_SourceIn)
        painter.fillRect(tinted.rect(), Qt.white)
        painter.end()
        return tinted

    return pm


def load_icons(size: int = 400, tint_white: bool = False) -> dict[str, QPixmap]:
    icons: dict[str, QPixmap] = {}
    for png_file in ICONS_DIR.glob("*.png"):
        icon_name = png_file.stem.lower()
        pm = png_to_pixmap(png_file, size=size, tint_white=tint_white)
        if not pm.isNull():
            icons[icon_name] = pm
            print(f"Loaded icon: {icon_name} from {png_file}")
    return icons


class Mirror(QWidget):
    def __init__(self, icons: dict[str, QPixmap]):

        super().__init__()
        self.setWindowTitle("Mirror")
        self.wallpaper = QPixmap(str(PICTURES_DIR / "background.png"))
        row_layout = QHBoxLayout()
        self.setGeometry(100, 100, 1080, 1920)

        self.phase_controller = PhaseIconController(
            icons, on_change=self.update)
        self.phase_controller.refresh()

        self.phase_timer = QTimer(self)
        self.phase_timer.timeout.connect(self.phase_controller.refresh)
        self.phase_timer.start(60_000)

        clock = QLabel("CLOCK", alignment=Qt.AlignLeft)
        clock.setObjectName("CLOCK")
        clock.setStyleSheet(style_for("clock"))

        main_layout = QVBoxLayout()
        main_layout.addLayout(row_layout)
        main_layout.addStretch(2)
        self.setLayout(main_layout)

        watch = PocketWatch(
            str(PICTURES_DIR / "watch.png"),
            str(PICTURES_DIR / "Watch_Hours.png"),
            str(PICTURES_DIR / "Watch_Minutes.png"),
            scale=0.5,
        )

        self.watch = watch
        self.watch.setParent(self)
        self.watch.show()

        clock_layout = QVBoxLayout()
        clock_layout.setSpacing(0)
        clock_layout.setContentsMargins(0, 20, 0, 0)

        hours = QLabel("hours", alignment=Qt.AlignLeft)
        hours.setObjectName("Hours")
        hours.setStyleSheet(style_for("hours"))

        minutes = QLabel("minutes", alignment=Qt.AlignLeft)
        minutes.setObjectName("Minutes")
        minutes.setStyleSheet(style_for("minutes"))

        seconds = QLabel("seconds", alignment=Qt.AlignLeft)
        seconds.setObjectName("Seconds")
        seconds.setStyleSheet(style_for("seconds"))

        date_layout = QVBoxLayout()

        week_day = QLabel("Monday", alignment=Qt.AlignRight)
        week_day.setObjectName("WEEK_DAY")
        week_day.setStyleSheet(style_for("week_day"))
        week_day.setFixedWidth(350)

        day = QLabel("12", alignment=Qt.AlignRight)
        day.setObjectName("DAY")
        day.setStyleSheet(style_for("day"))
        day.setFixedWidth(350)

        month = QLabel("12", alignment=Qt.AlignRight)
        month.setObjectName("MONTH")
        month.setStyleSheet(style_for("month"))
        month.setFixedWidth(350)

        year = QLabel("1923", alignment=Qt.AlignRight)
        year.setObjectName("YEAR")
        year.setStyleSheet(style_for("year"))
        year.setFixedWidth(350)

        date_layout.addWidget(week_day)
        date_layout.addWidget(day)
        date_layout.addWidget(month)
        date_layout.addWidget(year)
        date_layout.setSpacing(0)
        date_layout.addStretch(12)
        date_layout.setContentsMargins(170, 1300, 0, 0)

        clock_layout.addWidget(clock)
        clock_layout.addWidget(hours)
        clock_layout.addWidget(minutes)
        clock_layout.addWidget(seconds)
        clock_layout.addStretch()

        row_layout.addLayout(clock_layout)
        row_layout.addLayout(date_layout)
        row_layout.setAlignment(Qt.AlignLeft)
        row_layout.setSpacing(0)
        row_layout.setContentsMargins(40, 0, 0, 0)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.watch.move(int(self.width() * WATCH_POS[0]),
                        int(self.height() * WATCH_POS[1]))
        self.watch.raise_()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape:
            self.close()
        elif event.key() == Qt.Key_F11:
            if self.isFullScreen():
                self.showNormal()
            else:
                self.showFullScreen()
        else:
            super().keyPressEvent(event)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.drawPixmap(self.rect(), self.wallpaper)

        if self.phase_controller.current_pixmap:
            pm = self.phase_controller.current_pixmap
            xpos = -10
            ypos = -15
            x = self.width() - pm.width() - xpos
            y = ypos
            painter.drawPixmap(x, y, pm)

    def time(self, H, M, S):
        now = datetime.now()
        H.setText(now.strftime("H:%H"))
        M.setText(now.strftime("M:%M"))
        S.setText(now.strftime("S:%S"))

        self.findChild(QLabel, "WEEK_DAY").setText(now.strftime("%a"))
        self.findChild(QLabel, "DAY").setText(now.strftime("%d"))
        self.findChild(QLabel, "MONTH").setText(now.strftime("%b"))
        self.findChild(QLabel, "YEAR").setText(now.strftime("%Y"))

    def update_time(self, H, M, S):
        if None in (H, M, S):
            return
        self.time(H, M, S)  # Initial call to set the time immediately
        self.timer = QTimer(self)
        self.timer.timeout.connect(lambda: self.time(H, M, S))
        self.timer.start(1000)  # Update every second


if __name__ == "__main__":
    app = QApplication(sys.argv)
    load_fonts()
    icons = load_icons()
    mirror = Mirror(icons)
    mirror.showFullScreen()
    mirror.update_time(
        mirror.findChild(QLabel, "Hours"),
        mirror.findChild(QLabel, "Minutes"),
        mirror.findChild(QLabel, "Seconds")
    )
    sys.exit(app.exec())
