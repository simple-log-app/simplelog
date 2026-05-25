import atexit
import ctypes
import os
import sys

if sys.platform == "darwin" and hasattr(sys, "_MEIPASS"):
    qt6_dir = os.path.join(sys._MEIPASS, "PyQt6", "Qt6")
    qtcore_lib = os.path.join(sys._MEIPASS, "QtCore")

    if os.path.isdir(qt6_dir) and os.path.isfile(qtcore_lib):
        # macOS dyld resolves <weak-def-coalesce> imports by searching the global
        # symbol namespace.  When Qt framework dylibs are loaded with the default
        # RTLD_LOCAL (e.g. via a ctypes.CDLL() call or as an indirect dependency
        # of a Python extension), their weak_def exports are NOT visible for
        # coalescing.  This causes QtNetwork (and other Qt modules) to fail with
        # "Symbol not found: ... Expected as weak-def export from some loaded dylib"
        # when they try to coalesce QMetaTypeInterfaceWrapper<T> symbols from QtCore.
        #
        # Fix: pre-load all Qt framework dylibs with RTLD_GLOBAL so their weak_def
        # exports participate in coalescing.  We also register the qt.conf resource
        # that tells Qt where its prefix is inside the bundle.

        # Pre-load ALL Qt framework dylibs with RTLD_GLOBAL.
        # This must happen before any PyQt6.Qt* extension is imported.
        _qt_frameworks = [
            "QtCore", "QtDBus", "QtGui", "QtNetwork",
            "QtPdf", "QtSvg", "QtWidgets",
        ]
        for _fw in _qt_frameworks:
            _fw_path = os.path.join(sys._MEIPASS, _fw)
            if os.path.isfile(_fw_path):
                try:
                    ctypes.CDLL(_fw_path, ctypes.RTLD_GLOBAL)
                except OSError:
                    pass

        # Register :/qt/etc/qt.conf as a Qt resource so Qt's findConfiguration()
        # locates the correct prefix and never falls back to CFBundleCreate() on
        # the Frameworks/ directory (which is not a .app bundle and would crash).
        try:
            _qtcore = ctypes.CDLL(qtcore_lib, ctypes.RTLD_GLOBAL)

            _prefix = qt6_dir.replace(os.sep, "/")
            _conf = f"[Paths]\nPrefix = {_prefix}\n".encode()
            _data = len(_conf).to_bytes(4, "big") + _conf

            # Qt resource layout for :/qt/etc/qt.conf
            # (same constants as PyInstaller's _pyi_rth_utils/qt.py)
            _name = (
                b"\x00\x02\x00\x00\x07\x84\x00\x71\x00\x74"
                b"\x00\x03\x00\x00\x6c\xa3\x00\x65\x00\x74\x00\x63"
                b"\x00\x07\x08\x74\xa6\xa6"
                b"\x00\x71\x00\x74\x00\x2e\x00\x63\x00\x6f\x00\x6e\x00\x66"
            )
            _struct = (
                b"\x00\x00\x00\x00\x00\x02\x00\x00\x00\x01\x00\x00\x00\x01"
                b"\x00\x00\x00\x00\x00\x02\x00\x00\x00\x01\x00\x00\x00\x02"
                b"\x00\x00\x00\x0a\x00\x02\x00\x00\x00\x01\x00\x00\x00\x03"
                b"\x00\x00\x00\x16\x00\x00\x00\x00\x00\x01\x00\x00\x00\x00"
            )

            _reg = _qtcore._Z21qRegisterResourceDataiPKhS0_S0_
            _reg.restype = ctypes.c_bool
            _unreg = _qtcore._Z23qUnregisterResourceDataiPKhS0_S0_
            _unreg.restype = ctypes.c_bool

            if _reg(1, _struct, _name, _data):
                atexit.register(_unreg, 1, _struct, _name, _data)
        except (AttributeError, OSError):
            pass
