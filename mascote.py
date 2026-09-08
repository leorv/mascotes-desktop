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
        if self.character not in ('clippy', 'gato-preto', 'golden', 'panda', 'papagaio', 'yorkshire'):
            self.character = 'gato-preto'
        self.menu = QMenu()
        choices = self.menu.addMenu('Trocar bichinho')
        self.character_actions = QActionGroup(self)
        self.character_actions.setExclusive(True)
        for key, label in [('clippy', 'Clippy'), ('gato-preto', 'Pretí'), ('golden', 'Marla'), ('panda', 'Mochi'), ('papagaio', 'Louro José'), ('yorkshire', 'Zoe')]:
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

    def paint_golden(self, p, happy):
        # Honey fur, floppy ears and a fluffy chest from the golden reference.
        outline = QPen(QColor('#79502d'), 2.7, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
        p.setPen(outline)
        p.setBrush(QColor('#efb855'))
        p.save()
        p.translate(121, 191)
        p.rotate(0 if self.sleeping else math.sin(self.t * (12 if happy else 3)) * 9)
        tail = QPainterPath(QPointF(0, 12))
        tail.cubicTo(36, 16, 51, -19, 34, -48)
        tail.quadTo(36, -30, 26, -26)
        tail.lineTo(28, -38)
        tail.cubicTo(15, -21, 24, -7, 0, -6)
        tail.closeSubpath()
        p.drawPath(tail)
        p.restore()
        p.drawEllipse(QRectF(42, 128, 91, 86))
        p.setBrush(QColor('#ffda87'))
        chest = QPainterPath(QPointF(59, 139))
        chest.quadTo(86, 125, 112, 140)
        chest.lineTo(110, 161)
        chest.lineTo(104, 158)
        chest.lineTo(102, 180)
        chest.lineTo(95, 175)
        chest.lineTo(86, 190)
        chest.lineTo(76, 177)
        chest.lineTo(70, 181)
        chest.lineTo(68, 162)
        chest.lineTo(60, 166)
        chest.closeSubpath()
        p.setPen(Qt.NoPen)
        p.drawPath(chest)
        p.setPen(outline)
        p.setBrush(QColor('#f4c36c'))
        for x in (39, 103):
            p.drawEllipse(QRectF(x, 190, 33, 26))
        for x in (57, 88):
            p.drawRoundedRect(QRectF(x, 171, 31, 47), 12, 12)
            for offset in (10, 20):
                p.drawLine(QPointF(x + offset, 208), QPointF(x + offset, 215))
        p.setBrush(QColor('#f7c76e'))
        p.drawEllipse(QRectF(32, 47, 111, 105))
        # Soft hanging ears frame the face.
        for mirror in (False, True):
            p.save()
            if mirror:
                p.translate(175, 0)
                p.scale(-1, 1)
            ear = QPainterPath(QPointF(49, 58))
            ear.cubicTo(24, 54, 13, 79, 18, 106)
            ear.cubicTo(19, 120, 22, 135, 31, 135)
            ear.cubicTo(47, 131, 47, 98, 52, 79)
            ear.quadTo(57, 61, 49, 58)
            p.setBrush(QColor('#dda04a'))
            p.drawPath(ear)
            p.setPen(QPen(QColor('#efbb60'), 5, Qt.SolidLine, Qt.RoundCap))
            p.drawArc(QRectF(23, 71, 19, 51), 100 * 16, 100 * 16)
            p.restore()
        p.setPen(Qt.NoPen)
        p.setBrush(QColor('#ffdb8c'))
        tuft = QPainterPath(QPointF(63, 57))
        tuft.quadTo(71, 43, 84, 45)
        tuft.lineTo(79, 50)
        tuft.quadTo(94, 39, 109, 53)
        tuft.quadTo(89, 49, 80, 62)
        tuft.closeSubpath()
        p.drawPath(tuft)
        cursor = self.mapFromGlobal(QCursor.pos())
        for ex in (63, 112):
            p.setPen(QPen(QColor('#ad7637'), 3, Qt.SolidLine, Qt.RoundCap))
            p.drawArc(QRectF(ex - 11, 73, 21, 12), 25 * 16, 135 * 16)
            if self.sleeping or self.t % 4.7 < .12:
                p.setPen(outline)
                p.drawArc(QRectF(ex - 12, 94, 24, 13), 180 * 16, 180 * 16)
            else:
                p.setPen(Qt.NoPen)
                p.setBrush(QColor('#fff7e5'))
                p.drawEllipse(QRectF(ex - 13, 87, 26, 32))
                dx, dy = cursor.x() - ex, cursor.y() - 103
                distance = max(math.hypot(dx, dy), 1)
                px, py = ex + dx / distance * 3, 103 + dy / distance * 3
                p.setBrush(QColor('#694125'))
                p.drawEllipse(QPointF(px, py), 10.5, 14)
                p.setBrush(QColor('#35241d'))
                p.drawEllipse(QPointF(px, py), 7, 11)
                p.setBrush(Qt.white)
                p.drawEllipse(QPointF(px - 3, py - 5), 3, 3.5)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor('#ffdc92'))
        p.drawEllipse(QRectF(55, 110, 65, 33))
        p.setPen(outline)
        if self.sleeping:
            p.setBrush(Qt.NoBrush)
            p.drawArc(QRectF(73, 124, 28, 13), 180 * 16, 180 * 16)
        else:
            p.setBrush(QColor('#65382b'))
            smile = QPainterPath(QPointF(67, 128))
            smile.quadTo(87, 143, 109, 128)
            smile.quadTo(89, 162 if happy else 154, 67, 128)
            p.drawPath(smile)
            p.setPen(Qt.NoPen)
            p.setBrush(QColor('#ef9290'))
            p.drawRoundedRect(QRectF(81, 137, 16, 16 if happy else 12), 6, 6)
        p.setPen(outline)
        p.setBrush(QColor('#65412d'))
        nose = QPainterPath(QPointF(77, 116))
        nose.cubicTo(75, 110, 99, 110, 98, 117)
        nose.quadTo(88, 132, 77, 116)
        p.drawPath(nose)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor('#a77550'))
        p.drawEllipse(QRectF(80, 113, 8, 4))

    def paint_panda(self, p, happy):
        # Round ears, tilted eye patches and visible paw pads from the panda reference.
        outline = QPen(QColor('#242326'), 2.7, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
        p.setPen(outline)
        p.setBrush(QColor('#faf6ed'))
        p.drawEllipse(QRectF(25, 166, 31, 33))
        p.drawEllipse(QRectF(44, 127, 91, 84))
        p.setBrush(QColor('#303034'))
        p.drawEllipse(QRectF(47, 133, 84, 46))
        p.setPen(Qt.NoPen)
        p.setBrush(QColor('#faf6ed'))
        p.drawEllipse(QRectF(66, 144, 49, 62))
        p.setPen(outline)
        p.setBrush(QColor('#303034'))
        for x, angle in ((63, -16), (117, 16)):
            p.save()
            p.translate(x, 173)
            p.rotate(angle)
            p.drawEllipse(QRectF(-14, -30, 28, 66))
            p.restore()
        for x, angle in ((45, -23), (133, 23)):
            p.save()
            p.translate(x, 191)
            p.rotate(angle)
            p.setPen(outline)
            p.setBrush(QColor('#303034'))
            p.drawEllipse(QRectF(-23, -27, 46, 55))
            p.setPen(Qt.NoPen)
            p.setBrush(QColor('#80756f'))
            p.drawEllipse(QRectF(-11, -1, 22, 24))
            for tx, ty in ((-12, -12), (0, -17), (12, -12)):
                p.drawEllipse(QPointF(tx, ty), 4, 5)
            p.restore()
        p.setPen(outline)
        p.setBrush(QColor('#303034'))
        for x in (39, 133):
            p.drawEllipse(QPointF(x, 58), 24, 26)
            p.setPen(Qt.NoPen)
            p.setBrush(QColor('#414044'))
            p.drawEllipse(QPointF(x, 58), 14, 17)
            p.setPen(outline)
            p.setBrush(QColor('#303034'))
        p.setBrush(QColor('#faf6ed'))
        head = QPainterPath(QPointF(26, 100))
        head.cubicTo(26, 65, 53, 49, 81, 51)
        head.lineTo(91, 44)
        head.lineTo(91, 50)
        head.cubicTo(123, 49, 151, 73, 151, 106)
        head.cubicTo(155, 139, 130, 155, 90, 156)
        head.cubicTo(49, 156, 22, 140, 26, 100)
        p.drawPath(head)
        cursor = self.mapFromGlobal(QCursor.pos())
        for ex, angle in ((60, 24), (116, -24)):
            p.save()
            p.translate(ex, 105)
            p.rotate(angle)
            p.setPen(Qt.NoPen)
            p.setBrush(QColor('#303034'))
            p.drawEllipse(QRectF(-19, -27, 38, 53))
            p.restore()
            if self.sleeping or self.t % 4.7 < .12:
                p.setPen(QPen(QColor('#eee6dc'), 2.5, Qt.SolidLine, Qt.RoundCap))
                p.drawArc(QRectF(ex - 10, 100, 20, 12), 180 * 16, 180 * 16)
            else:
                p.setPen(Qt.NoPen)
                p.setBrush(QColor('#fffaf0'))
                p.drawEllipse(QRectF(ex - 12, 93, 24, 30))
                dx, dy = cursor.x() - ex, cursor.y() - 108
                distance = max(math.hypot(dx, dy), 1)
                px, py = ex + dx / distance * 2.5, 108 + dy / distance * 2.5
                p.setBrush(QColor('#392f2a'))
                p.drawEllipse(QPointF(px, py), 10, 13)
                p.setBrush(QColor('#19191c'))
                p.drawEllipse(QPointF(px, py), 7, 10)
                p.setBrush(Qt.white)
                p.drawEllipse(QPointF(px - 3, py - 5), 3.2, 3.7)
            p.setPen(QPen(QColor('#303034'), 3, Qt.SolidLine, Qt.RoundCap))
            p.drawArc(QRectF(ex - 9, 70, 18, 11), 25 * 16, 130 * 16)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor('#e8e0d7'))
        p.drawEllipse(QRectF(75, 117, 28, 17))
        p.setPen(outline)
        p.setBrush(QColor('#303034'))
        nose = QPainterPath(QPointF(80, 122))
        nose.cubicTo(75, 117, 99, 117, 98, 122)
        nose.quadTo(89, 134, 80, 122)
        p.drawPath(nose)
        p.drawLine(QPointF(89, 129), QPointF(89, 134))
        p.setBrush(Qt.NoBrush)
        if self.sleeping:
            p.drawArc(QRectF(78, 130, 22, 11), 180 * 16, 180 * 16)
        else:
            p.setBrush(QColor('#633d3b'))
            mouth = QPainterPath(QPointF(77, 134))
            mouth.quadTo(89, 141, 102, 133)
            mouth.quadTo(91, 158 if happy else 151, 77, 134)
            p.drawPath(mouth)
            p.setPen(Qt.NoPen)
            p.setBrush(QColor('#ed9c9c'))
            p.drawEllipse(QRectF(85, 139, 12, 8 if happy else 5))

    def paint_parrot(self, p, happy):
        # Profile, orange beak and half-lidded eye from the user's updated reference.
        outline = QPen(QColor('#29292a'), 2.5, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
        p.setPen(outline)
        p.setBrush(QColor('#175c32'))
        tail = QPainterPath(QPointF(46, 183))
        tail.cubicTo(16, 187, 12, 135, 23, 132)
        tail.quadTo(41, 133, 56, 161)
        tail.closeSubpath()
        p.drawPath(tail)
        p.drawEllipse(QRectF(35, 112, 105, 96))
        p.setPen(Qt.NoPen)
        p.setBrush(QColor('#eee914'))
        belly = QPainterPath(QPointF(136, 159))
        belly.cubicTo(101, 159, 91, 182, 94, 199)
        belly.cubicTo(120, 203, 139, 181, 136, 159)
        p.drawPath(belly)
        p.setPen(outline)
        for x in (105, 63):
            p.setBrush(QColor('#e94722'))
            p.drawRoundedRect(QRectF(x - 16, 196, 40, 22), 10, 10)
            p.drawArc(QRectF(x + 5, 196, 12, 22), -80 * 16, 160 * 16)
            p.drawArc(QRectF(x - 5, 196, 12, 22), -80 * 16, 160 * 16)
        p.save()
        p.translate(53, 137)
        p.rotate(-abs(math.sin(self.t * 13)) * 16 if happy and not self.sleeping else 0)
        p.setBrush(QColor('#175c32'))
        wing = QPainterPath(QPointF(0, -8))
        wing.cubicTo(-24, 3, -36, 30, -31, 46)
        wing.cubicTo(-19, 58, 17, 32, 18, 5)
        wing.closeSubpath()
        p.drawPath(wing)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor('#eee914'))
        patch = QPainterPath(QPointF(-2, -3))
        patch.cubicTo(-18, 6, -29, 28, -30, 40)
        patch.cubicTo(-14, 36, -4, 16, -2, -3)
        p.drawPath(patch)
        p.restore()
        p.setPen(outline)
        p.setBrush(QColor('#175c32'))
        head = QPainterPath(QPointF(43, 121))
        head.cubicTo(33, 93, 33, 55, 54, 40)
        head.cubicTo(76, 19, 117, 29, 128, 56)
        head.lineTo(134, 125)
        head.quadTo(136, 148, 115, 143)
        head.quadTo(99, 158, 83, 144)
        head.quadTo(61, 151, 54, 135)
        head.quadTo(31, 141, 43, 121)
        p.drawPath(head)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor('#eeeb12'))
        face = QPainterPath(QPointF(49, 112))
        face.cubicTo(39, 83, 43, 54, 67, 44)
        face.cubicTo(89, 34, 118, 42, 126, 64)
        face.lineTo(132, 121)
        face.quadTo(128, 138, 113, 130)
        face.quadTo(100, 143, 85, 132)
        face.quadTo(68, 139, 62, 124)
        face.quadTo(48, 131, 49, 112)
        p.drawPath(face)
        p.setPen(outline)
        # Curved yellow forehead feathers, with no upright crest.
        for x, y in ((77, 38), (91, 37), (104, 41)):
            feather = QPainterPath(QPointF(x, y))
            feather.quadTo(x + 19, y + 3, x + 20, y + 18)
            feather.quadTo(x + 17, y + 25, x + 9, y + 15)
            p.setBrush(QColor('#eeeb12'))
            p.drawPath(feather)
        ex, ey = 69, 84
        p.setBrush(QColor('#fffdf8'))
        p.drawEllipse(QRectF(52, 65, 34, 38))
        if self.sleeping or self.t % 4.7 < .12:
            p.setBrush(QColor('#f2d3dd'))
            p.drawEllipse(QRectF(52, 65, 34, 38))
            p.drawArc(QRectF(56, 79, 26, 12), 180 * 16, 180 * 16)
        else:
            cursor = self.mapFromGlobal(QCursor.pos())
            dx, dy = self.width() - cursor.x() - ex, cursor.y() - ey
            distance = max(math.hypot(dx, dy), 1)
            p.setPen(Qt.NoPen)
            p.setBrush(QColor('#242124'))
            p.drawEllipse(QPointF(ex + dx / distance * 3, ey + 4 + dy / distance * 2), 11, 12)
            p.setPen(outline)
            p.setBrush(QColor('#f2d3dd'))
            lid = QPainterPath(QPointF(52, 84 if not happy else 77))
            lid.cubicTo(50, 59, 79, 58, 85, 77 if not happy else 70)
            lid.quadTo(72, 86 if not happy else 80, 52, 84 if not happy else 77)
            p.drawPath(lid)
        p.setPen(outline)
        p.setBrush(QColor('#ac5697'))
        p.drawEllipse(QRectF(107, 94, 46, 34))
        p.setBrush(QColor('#e74721'))
        lower = QPainterPath(QPointF(96, 102))
        lower.quadTo(113, 123, 158, 124 if not happy else 129)
        lower.cubicTo(161, 151, 119, 145, 103, 130)
        lower.quadTo(87, 116, 96, 102)
        p.drawPath(lower)
        beak = QPainterPath(QPointF(94, 76))
        beak.cubicTo(100, 64, 119, 61, 135, 59)
        beak.cubicTo(157, 54, 170, 78, 169, 99)
        beak.quadTo(170, 108, 156, 105)
        beak.cubicTo(136, 102, 126, 109, 115, 117)
        beak.quadTo(97, 114, 92, 101)
        beak.quadTo(88, 95, 94, 76)
        p.drawPath(beak)

    def paint_yorkshire(self, p, happy):
        # Silky tan and gray coat, pointed ears and beard from yorkshire.png.
        outline = QPen(QColor('#514238'), 2.5, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
        p.setPen(outline)
        p.setBrush(QColor('#64636a'))
        p.save()
        p.translate(123, 185)
        p.rotate(0 if self.sleeping else math.sin(self.t * (12 if happy else 3)) * 9)
        tail = QPainterPath(QPointF(-4, 15))
        tail.cubicTo(33, 18, 49, -15, 27, -39)
        tail.quadTo(33, -20, 19, -18)
        tail.lineTo(23, -28)
        tail.cubicTo(11, -14, 20, -5, -4, -1)
        tail.closeSubpath()
        p.drawPath(tail)
        p.setPen(QPen(QColor('#dba25d'), 5, Qt.SolidLine, Qt.RoundCap))
        p.drawArc(QRectF(9, -19, 23, 30), -90 * 16, 120 * 16)
        p.restore()
        p.drawEllipse(QRectF(44, 128, 88, 83))
        p.setBrush(QColor('#edba78'))
        p.drawEllipse(QRectF(101, 185, 34, 29))
        chest = QPainterPath(QPointF(62, 136))
        chest.quadTo(83, 128, 107, 139)
        chest.lineTo(110, 160)
        chest.lineTo(104, 156)
        chest.lineTo(101, 178)
        chest.lineTo(92, 171)
        chest.lineTo(84, 192)
        chest.lineTo(74, 177)
        chest.lineTo(66, 181)
        chest.lineTo(63, 161)
        chest.lineTo(56, 165)
        chest.closeSubpath()
        p.drawPath(chest)
        for x in (49, 88):
            p.drawRoundedRect(QRectF(x, 169, 33, 48), 12, 12)
            for offset in (10, 21):
                p.drawLine(QPointF(x + offset, 207), QPointF(x + offset, 214))
        p.setBrush(QColor('#64636a'))
        ears = QPainterPath(QPointF(34, 88))
        ears.lineTo(25, 36)
        ears.quadTo(27, 30, 34, 36)
        ears.lineTo(69, 62)
        ears.lineTo(109, 60)
        ears.lineTo(140, 30)
        ears.lineTo(146, 68)
        ears.lineTo(140, 93)
        ears.closeSubpath()
        p.drawPath(ears)
        p.setBrush(QColor('#eab475'))
        for points in (((32, 42), (40, 83), (62, 64)), ((136, 40), (114, 64), (137, 81))):
            ear = QPainterPath(QPointF(*points[0]))
            for point in points[1:]:
                ear.lineTo(*point)
            ear.closeSubpath()
            p.drawPath(ear)
        p.setBrush(QColor('#d68f69'))
        p.setPen(Qt.NoPen)
        p.drawEllipse(QRectF(37, 51, 12, 22))
        p.drawEllipse(QRectF(125, 50, 10, 22))
        p.setPen(outline)
        p.setBrush(QColor('#64636a'))
        p.drawEllipse(QRectF(25, 58, 123, 98))
        p.setBrush(QColor('#edba78'))
        face = QPainterPath(QPointF(83, 88))
        face.cubicTo(62, 60, 35, 77, 34, 108)
        face.lineTo(29, 126)
        face.lineTo(36, 122)
        face.quadTo(36, 149, 62, 150)
        face.quadTo(88, 163, 115, 149)
        face.quadTo(141, 147, 140, 122)
        face.lineTo(146, 126)
        face.cubicTo(138, 76, 111, 61, 91, 88)
        face.lineTo(87, 69)
        face.closeSubpath()
        p.drawPath(face)
        p.setPen(QPen(QColor('#d99c60'), 2, Qt.SolidLine, Qt.RoundCap))
        for x in (48, 61, 109, 122):
            p.drawArc(QRectF(x - 8, 77, 20, 31), 35 * 16, 100 * 16)
        cursor = self.mapFromGlobal(QCursor.pos())
        for ex in (61, 113):
            if self.sleeping or self.t % 4.7 < .12:
                p.setPen(outline)
                p.drawArc(QRectF(ex - 12, 102, 24, 12), 180 * 16, 180 * 16)
            else:
                p.setPen(Qt.NoPen)
                p.setBrush(QColor('#fff4e1'))
                p.drawEllipse(QRectF(ex - 13, 92, 26, 31))
                dx, dy = cursor.x() - ex, cursor.y() - 107
                distance = max(math.hypot(dx, dy), 1)
                px, py = ex + dx / distance * 3, 107 + dy / distance * 3
                p.setBrush(QColor('#63422b'))
                p.drawEllipse(QPointF(px, py), 11, 14)
                p.setBrush(QColor('#211e1d'))
                p.drawEllipse(QPointF(px, py), 8, 11)
                p.setBrush(Qt.white)
                p.drawEllipse(QPointF(px - 3, py - 5), 3.2, 3.8)
        p.setPen(outline)
        p.setBrush(QColor('#f3c58c'))
        beard = QPainterPath(QPointF(86, 124))
        beard.cubicTo(64, 115, 50, 125, 50, 142)
        beard.lineTo(56, 138)
        beard.quadTo(61, 156, 74, 151)
        beard.lineTo(84, 161)
        beard.lineTo(94, 151)
        beard.quadTo(117, 157, 123, 136)
        beard.lineTo(127, 140)
        beard.cubicTo(124, 120, 103, 116, 86, 124)
        p.drawPath(beard)
        p.setBrush(Qt.NoBrush)
        p.drawArc(QRectF(73, 129, 28, 14), 180 * 16, 180 * 16)
        if not self.sleeping:
            p.setBrush(QColor('#ed9491'))
            p.drawRoundedRect(QRectF(82, 137, 13, 14 if happy else 9), 5, 5)
        p.setBrush(QColor('#302927'))
        p.drawRoundedRect(QRectF(77, 122, 21, 12), 6, 6)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor('#9b8c7e'))
        p.drawEllipse(QRectF(80, 124, 8, 3))

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
        elif self.character == 'golden':
            self.paint_golden(p, happy)
        elif self.character == 'panda':
            self.paint_panda(p, happy)
        elif self.character == 'yorkshire':
            self.paint_yorkshire(p, happy)
        elif self.character == 'papagaio':
            p.save()
            p.translate(self.width(), 0)
            p.scale(-1, 1)
            self.paint_parrot(p, happy)
            p.restore()
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
