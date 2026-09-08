#!/usr/bin/python3
"""Mascote local para Linux/X11 e Windows.

Não lê teclas, conteúdo de janelas ou rede. Só consulta a posição e os botões
do mouse para animar o mascote.
"""
import ctypes as C
import ctypes.util
from ctypes import wintypes
import math
import os
from pathlib import Path
import sys
import time
from PyQt5.QtCore import Qt, QTimer, QPointF, QRectF, QLockFile, QStandardPaths, QSettings
from PyQt5.QtGui import QColor, QPainter, QPainterPath, QPen, QCursor, QIcon, QFont
from PyQt5.QtWidgets import QApplication, QWidget, QMenu, QSystemTrayIcon, QActionGroup

BASE = Path(__file__).resolve().parent
IS_WINDOWS = os.name == 'nt'
if IS_WINDOWS:
    APPDATA = Path(os.environ.get('APPDATA', Path.home() / 'AppData/Roaming'))
    AUTOSTART = APPDATA / 'Microsoft/Windows/Start Menu/Programs/Startup/Mascote Clips.bat'
    WINDOWS_PYTHON = Path(sys.executable).with_name('pythonw.exe')
    if not WINDOWS_PYTHON.exists():
        WINDOWS_PYTHON = Path(sys.executable)
    STARTUP_TEXT = f'@start "" "{WINDOWS_PYTHON}" "{BASE / "mascote.py"}"\n'
else:
    AUTOSTART = Path.home() / '.config/autostart/mascote-clips.desktop'
    STARTUP_TEXT = f'''[Desktop Entry]
Type=Application
Name=Clips — Mascote do PC
Comment=Um clipe animado que acompanha o mouse
Exec="{sys.executable}" "{BASE / 'mascote.py'}"
Icon=face-smile
Terminal=false
Categories=Game;
'''

class LinuxPointer:
    def __init__(self):
        library = ctypes.util.find_library('X11')
        if not library:
            raise RuntimeError('A biblioteca X11 não está disponível.')
        self.x = C.CDLL(library)
        self.x.XOpenDisplay.argtypes = [C.c_char_p]
        self.x.XOpenDisplay.restype = C.c_void_p
        self.d = self.x.XOpenDisplay(None)
        if not self.d:
            raise RuntimeError('Não foi possível acessar a sessão X11.')
        self.x.XDefaultRootWindow.argtypes = [C.c_void_p]
        self.x.XDefaultRootWindow.restype = C.c_ulong
        self.root = self.x.XDefaultRootWindow(self.d)
        self.x.XQueryPointer.argtypes = [C.c_void_p, C.c_ulong, C.POINTER(C.c_ulong), C.POINTER(C.c_ulong), *([C.POINTER(C.c_int)] * 4), C.POINTER(C.c_uint)]
        self.x.XQueryPointer.restype = C.c_int
        self.x.XCloseDisplay.argtypes = [C.c_void_p]
    def read(self):
        root, child = C.c_ulong(), C.c_ulong()
        rx, ry, wx, wy = (C.c_int() for _ in range(4))
        mask = C.c_uint()
        self.x.XQueryPointer(self.d, self.root, C.byref(root), C.byref(child), C.byref(rx), C.byref(ry), C.byref(wx), C.byref(wy), C.byref(mask))
        return rx.value, ry.value, mask.value & 0x1f00
    def close(self):
        self.x.XCloseDisplay(self.d)


class WindowsPointer:
    """Consulta o cursor e os botões sem depender de pacotes extras."""

    class Point(C.Structure):
        _fields_ = [('x', C.c_long), ('y', C.c_long)]

    def __init__(self):
        self.user32 = C.WinDLL('user32', use_last_error=True)
        self.user32.GetCursorPos.argtypes = [C.POINTER(self.Point)]
        self.user32.GetCursorPos.restype = wintypes.BOOL
        self.user32.GetAsyncKeyState.argtypes = [C.c_int]
        self.user32.GetAsyncKeyState.restype = C.c_short

    def read(self):
        point = self.Point()
        if not self.user32.GetCursorPos(C.byref(point)):
            raise C.WinError(C.get_last_error())
        buttons = 0
        if self.user32.GetAsyncKeyState(0x01) & 0x8000:
            buttons |= 1
        if self.user32.GetAsyncKeyState(0x02) & 0x8000:
            buttons |= 2
        return point.x, point.y, buttons

    def close(self):
        pass


def create_pointer():
    return WindowsPointer() if IS_WINDOWS else LinuxPointer()

class Pet(QWidget):
    def __init__(self, pointer):
        super().__init__(None, Qt.Tool | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.WindowDoesNotAcceptFocus)
        self.setWindowTitle('Clips — Mascote do PC')
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self.setFixedSize(180, 240)
        self.setCursor(Qt.OpenHandCursor)
        self.setToolTip('Arraste para mover • Botão direito para opções')
        self.pointer = pointer
        self.previous = pointer.read()
        self.last_move = time.monotonic()
        self.clicked_until = 0
        self.drag = None
        self.paused = False
        self.sleeping = False
        self.t = 0
        self.message_until = time.monotonic() + 7
        self.settings = QSettings('MascoteDoPC', 'Mascotes')
        self.character = self.settings.value('bichinho', 'gato-preto')
        if self.character not in ('clippy', 'gato-preto'):
            self.character = 'gato-preto'
        self.menu = QMenu()
        choices = self.menu.addMenu('Trocar bichinho')
        self.character_actions = QActionGroup(self)
        self.character_actions.setExclusive(True)
        for key, label in [('clippy', 'Clippy'), ('gato-preto', 'Gato preto')]:
            action = choices.addAction(label)
            action.setCheckable(True)
            action.setData(key)
            action.setChecked(key == self.character)
            self.character_actions.addAction(action)
        self.character_actions.triggered.connect(self.change_character)
        self.menu.addSeparator()
        self.menu.addAction('Mostrar / esconder', self.toggle_visible)
        self.pause_action = self.menu.addAction('Pausar reações', self.toggle_pause)
        self.pause_action.setCheckable(True)
        self.start_action = self.menu.addAction('Iniciar com o computador', self.toggle_start)
        self.start_action.setCheckable(True)
        self.start_action.setChecked(AUTOSTART.is_file())
        self.menu.addSeparator()
        self.menu.addAction('Sair', QApplication.instance().quit)
        self.tray = QSystemTrayIcon(QIcon.fromTheme('face-smile'), self)
        self.tray.setToolTip('Clips — Mascote do PC')
        self.tray.setContextMenu(self.menu)
        self.tray.activated.connect(lambda reason: self.toggle_visible() if reason == QSystemTrayIcon.Trigger else None)
        self.tray.show()
        r = QApplication.primaryScreen().availableGeometry()
        self.move(r.right() - self.width() - 24, r.bottom() - self.height() - 12)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.tick)
        self.timer.start(33)
    def change_character(self, action):
        self.character = action.data()
        self.settings.setValue('bichinho', self.character)
        self.update()

    def toggle_visible(self):
        self.setVisible(not self.isVisible())
    def toggle_pause(self, checked):
        self.paused = checked
    def toggle_start(self, checked):
        if checked:
            AUTOSTART.parent.mkdir(parents=True, exist_ok=True)
            AUTOSTART.write_text(STARTUP_TEXT, encoding='utf-8')
        else:
            AUTOSTART.unlink(missing_ok=True)
    def tick(self):
        now = time.monotonic()
        current = self.pointer.read()
        if current != self.previous:
            self.last_move = now
        if current[2] & ~self.previous[2]:
            self.clicked_until = now + .65
        self.previous = current
        if not self.paused:
            self.t = now
            self.sleeping = now - self.last_move > 35
            self.update()
    def mousePressEvent(self, event):
        if event.button() == Qt.RightButton:
            self.menu.popup(event.globalPos())
        elif event.button() == Qt.LeftButton:
            self.drag = event.globalPos() - self.pos()
            self.setCursor(Qt.ClosedHandCursor)
    def mouseMoveEvent(self, event):
        if self.drag is not None:
            self.move(event.globalPos() - self.drag)
    def mouseReleaseEvent(self, event):
        self.drag = None
        self.setCursor(Qt.OpenHandCursor)
        screen = QApplication.screenAt(self.frameGeometry().center()) or QApplication.primaryScreen()
        r = screen.availableGeometry()
        self.move(max(r.left(), min(self.x(), r.right() - self.width() + 1)), max(r.top(), min(self.y(), r.bottom() - self.height() + 1)))
    def paint_cat(self, p, happy):
        # Rounded silhouette and golden eyes based on referencias-mascotes/gato-preto.png.
        outline = QPen(QColor('#171719'), 3, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
        p.setPen(QPen(QColor('#171719'), 22, Qt.SolidLine, Qt.RoundCap))
        tail = QPainterPath(QPointF(119, 202))
        tail.cubicTo(170, 205, 166, 144, 148, 151)
        tail.cubicTo(139, 154, 143, 166, 148, 165)
        p.drawPath(tail)
        p.setPen(QPen(QColor('#303034'), 16, Qt.SolidLine, Qt.RoundCap))
        p.drawPath(tail)
        p.setPen(outline)
        p.setBrush(QColor('#29292d'))
        p.drawEllipse(QRectF(43, 128, 87, 87))
        p.setBrush(QColor('#343438'))
        p.drawEllipse(QRectF(62, 144, 45, 65))
        for x in (49, 91):
            p.setPen(outline)
            p.setBrush(QColor('#29292d'))
            p.drawRoundedRect(QRectF(x, 179, 33, 37), 13, 13)
            p.drawLine(QPointF(x + 11, 204), QPointF(x + 11, 213))
            p.drawLine(QPointF(x + 21, 204), QPointF(x + 21, 213))
        ears = QPainterPath(QPointF(32, 96))
        ears.lineTo(29, 39)
        ears.quadTo(31, 29, 40, 38)
        ears.lineTo(68, 66)
        ears.lineTo(111, 65)
        ears.lineTo(136, 37)
        ears.quadTo(144, 30, 144, 42)
        ears.lineTo(140, 100)
        ears.closeSubpath()
        p.drawPath(ears)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor('#e998a0'))
        for points in (((37, 47), (40, 85), (60, 70)), ((136, 47), (116, 72), (136, 86))):
            ear = QPainterPath(QPointF(*points[0]))
            for point in points[1:]:
                ear.lineTo(*point)
            ear.closeSubpath()
            p.drawPath(ear)
        p.setPen(outline)
        p.setBrush(QColor('#29292d'))
        p.drawEllipse(QRectF(24, 62, 123, 97))
        cursor = self.mapFromGlobal(QCursor.pos())
        for ex in (58, 111):
            if self.sleeping or self.t % 4.7 < .12:
                p.setPen(QPen(QColor('#e6b64f'), 3, Qt.SolidLine, Qt.RoundCap))
                p.drawArc(QRectF(ex - 15, 98, 30, 15), 180 * 16, 180 * 16)
            else:
                p.setPen(outline)
                p.setBrush(QColor('#efbd4f'))
                p.drawEllipse(QRectF(ex - 17, 87, 34, 41))
                dx, dy = cursor.x() - ex, cursor.y() - 107
                distance = max(math.hypot(dx, dy), 1)
                px, py = ex + dx / distance * 5, 107 + dy / distance * 4
                p.setPen(Qt.NoPen)
                p.setBrush(QColor('#151518'))
                p.drawEllipse(QPointF(px, py), 10, 16)
                p.setBrush(Qt.white)
                p.drawEllipse(QPointF(px - 3, py - 6), 3.5, 4)
        p.setPen(outline)
        p.setBrush(QColor('#151518'))
        p.drawEllipse(QRectF(79, 123, 12, 7))
        mouth = QPainterPath(QPointF(85, 130))
        mouth.lineTo(85, 135)
        mouth.cubicTo(79, 142, 73, 137, 73, 134)
        p.setBrush(Qt.NoBrush)
        p.drawPath(mouth)
        p.drawArc(QRectF(85, 129, 13, 11), 180 * 16, 180 * 16)
        if happy:
            p.setBrush(QColor('#ed929c'))
            p.drawRoundedRect(QRectF(81, 136, 10, 11), 4, 4)
        p.setPen(QPen(QColor('#828187'), 1.2, Qt.SolidLine, Qt.RoundCap))
        for y, offset in ((126, -4), (134, 3)):
            p.drawLine(QPointF(45, y), QPointF(15, y + offset))
            p.drawLine(QPointF(126, y), QPointF(157, y + offset))

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        happy = self.t < self.clicked_until
        bounce = -abs(math.sin(self.t * 15)) * 9 if happy else math.sin(self.t * 2) * 2
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(0, 0, 0, 28))
        p.drawEllipse(QRectF(39, 220, 105, 9))
        p.translate(0, bounce)
        if self.character == 'gato-preto':
            self.paint_cat(p, happy)
        else:
            wire = QPainterPath(QPointF(120, 118))
            wire.cubicTo(112, 141, 123, 195, 96, 205)
            wire.cubicTo(36, 231, 43, 158, 46, 114)
            wire.lineTo(56, 60)
            wire.cubicTo(63, 19, 117, 23, 116, 65)
            wire.lineTo(103, 151)
            wire.cubicTo(97, 186, 65, 180, 69, 150)
            wire.lineTo(75, 116)
            p.setBrush(Qt.NoBrush)
            for color, width in [('#44445f', 14), ('#aaa9c7', 10), ('#d9daec', 4)]:
                p.setPen(QPen(QColor(color), width, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
                p.drawPath(wire)
            cursor = self.mapFromGlobal(QCursor.pos())
            blink = self.t % 4.7 < .12
            for ex, ey in [(61, 86), (111, 99)]:
                p.setPen(QPen(QColor('#77778e'), 1.5))
                p.setBrush(QColor('#fcfcff'))
                p.drawEllipse(QRectF(ex - 25, ey - 22, 50, 44))
                p.setPen(QPen(QColor('#29283b'), 3, Qt.SolidLine, Qt.RoundCap))
                if self.sleeping or blink:
                    p.drawArc(QRectF(ex - 13, ey - 6, 26, 13), 180 * 16, 180 * 16)
                else:
                    dx, dy = cursor.x() - ex, cursor.y() - ey
                    distance = max(math.hypot(dx, dy), 1)
                    px, py = ex + dx / distance * 8, ey + dy / distance * 7
                    p.setPen(Qt.NoPen)
                    p.setBrush(QColor('#21212c'))
                    p.drawEllipse(QPointF(px, py), 11, 13 if not happy else 10)
                    p.setBrush(Qt.white)
                    p.drawEllipse(QPointF(px - 3, py - 4), 3.5, 3.5)
                p.setPen(QPen(QColor('#333344'), 4, Qt.SolidLine, Qt.RoundCap))
                p.drawArc(QRectF(ex - 22, ey - 37 - (5 if happy else 0), 42, 20), 30 * 16, 130 * 16)
        p.setPen(QColor('#65617f'))
        p.setFont(QFont('Sans Serif', 13, QFont.Bold))
        if self.sleeping:
            p.drawText(131, 50, 'z Z')
        elif happy:
            p.setPen(QColor('#d8874a'))
            p.drawText(139, 67, '✦')
        if time.monotonic() < self.message_until:
            p.setPen(Qt.NoPen)
            p.setBrush(QColor('#fffaee'))
            p.drawRoundedRect(QRectF(9, 2, 160, 25), 10, 10)
            p.setPen(QColor('#44415a'))
            p.setFont(QFont('Sans Serif', 10))
            p.drawText(QRectF(9, 2, 160, 25), Qt.AlignCenter, 'Oi! Vou ficar por aqui.')
        p.end()

if __name__ == '__main__':
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    lock_root = QStandardPaths.writableLocation(QStandardPaths.RuntimeLocation)
    if not lock_root:
        lock_root = QStandardPaths.writableLocation(QStandardPaths.AppDataLocation) or str(BASE)
    lock = QLockFile(str(Path(lock_root) / 'mascote-clips.lock'))
    if not lock.tryLock(100):
        sys.exit(0)
    pointer = create_pointer()
    app.aboutToQuit.connect(pointer.close)
    pet = Pet(pointer)
    pet.show()
    if '--preview' in sys.argv:
        QTimer.singleShot(300, lambda: pet.grab().save(str(BASE / 'preview.png')))
        QTimer.singleShot(500, app.quit)
    sys.exit(app.exec_())
