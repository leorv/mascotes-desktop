"""Exercise all poses and optionally the standalone binary in isolated settings."""
import os
import atexit
from pathlib import Path
import runpy
import subprocess
import sys
import tempfile
import time
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def main():
    with tempfile.TemporaryDirectory(prefix='clips-test-') as temporary:
        root = Path(temporary)
        os.environ['XDG_CONFIG_HOME'] = str(root / 'config')
        os.environ['XDG_RUNTIME_DIR'] = str(root / 'runtime')
        (root / 'runtime').mkdir(mode=0o700)
        from PyQt5.QtCore import QSettings
        from PyQt5.QtGui import QImage
        from PyQt5.QtWidgets import QApplication
        import mascote

        if mascote.IS_WINDOWS:
            settings_backup = QSettings('MascoteDoPC', 'Mascotes')
            previous = {key: settings_backup.value(key) for key in settings_backup.allKeys()}
            def restore_settings():
                settings_backup.clear()
                for key, value in previous.items():
                    settings_backup.setValue(key, value)
                settings_backup.sync()
            atexit.register(restore_settings)

        executable = '/home/example/Meus mascotes/Clips 1.0'
        with patch.object(sys, 'frozen', True, create=True), patch.object(sys, 'executable', executable):
            frozen = runpy.run_path(str(Path(mascote.__file__)))
        if not mascote.IS_WINDOWS:
            assert f'Exec="{executable}"\n' in frozen['STARTUP_TEXT']
            assert 'mascote.py' not in frozen['STARTUP_TEXT']
        else:
            assert frozen['STARTUP_TEXT'] == f'@start "" "{executable}"\n'

        class Pointer:
            def read(self):
                return 100, 100, 0

        app = QApplication([])
        pet = mascote.Pet(Pointer())
        assert not pet.tray.icon().isNull(), 'Missing system tray icon'
        mascote.AUTOSTART = root / 'startup' / 'clips.bat'
        pet.toggle_start(True)
        assert mascote.AUTOSTART.read_text(encoding='utf-8') == mascote.STARTUP_TEXT
        pet.toggle_start(False)
        assert not mascote.AUTOSTART.exists()
        pet.timer.stop()
        pet.show()
        app.processEvents()
        assert len(pet.mixi_poses) == 10
        assert all(not image.isNull() for image in pet.mixi_poses.values()), 'Missing Mixi asset'
        for action in pet.character_actions.actions():
            pet.change_character(action)
            for mirrored in (False, True):
                pet.toggle_mirror(mirrored)
                for state in ('normal', 'happy', 'sleeping'):
                    pet.t = time.monotonic()
                    pet.sleeping = state == 'sleeping'
                    pet.clicked_until = pet.t + 1 if state == 'happy' else 0
                    assert not pet.grab().isNull(), (action.data(), mirrored, state)
        pet.tray.hide()
        pet.close()
        if len(sys.argv) > 1:
            binary = str(Path(sys.argv[1]).resolve())
            if not mascote.IS_WINDOWS:
                version = subprocess.check_output([binary, '--version'], text=True, timeout=30)
                assert version.strip() == f'Clips — Mascote do PC {mascote.VERSION}'
            settings = QSettings('MascoteDoPC', 'Mascotes')
            settings.setValue('bichinho', 'mixi')
            settings.setValue('mixi_split_v1', True)
            for mirrored in (False, True):
                settings.setValue('espelhar_mascote', mirrored)
                settings.sync()
                preview = root / 'preview.png'
                preview.unlink(missing_ok=True)
                subprocess.run([binary, '--preview'], cwd=root, check=True, timeout=30)
                image = QImage(str(preview))
                assert not image.isNull(), 'Packaged app did not render a preview'
                assert (image.width(), image.height()) == (180, 240)
        print('OK: 8 mascots, 48 poses, 10 bundled assets' +
              (', standalone mirrored Mixi previews' if len(sys.argv) > 1 else ''))


if __name__ == '__main__':
    main()
