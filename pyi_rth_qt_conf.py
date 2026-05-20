import atexit
import os
import sys

if sys.platform == "darwin" and hasattr(sys, "_MEIPASS"):
    import ctypes

    qt6_dir = os.path.join(sys._MEIPASS, "PyQt6", "Qt6")
    qtcore_lib = os.path.join(sys._MEIPASS, "QtCore")

    if os.path.isdir(qt6_dir) and os.path.isfile(qtcore_lib):
        # Qt 6.11+ includes a static initializer in QtCore.abi3.so that calls
        # QLibraryInfo::path() before QCoreApplication is created.  Qt then tries
        # CFBundleCreate() on the PyInstaller Frameworks/ directory (not a .app
        # bundle), gets NULL back, and crashes inside CFBundleCopyBundleURL(NULL).
        #
        # Fix: pre-register :/qt/etc/qt.conf as a Qt resource *before* PyQt6.QtCore
        # is imported (this hook runs before PyInstaller's pyi_rth_pyqt6 hook).
        # Qt's findConfiguration() finds the resource, reads the correct prefix, and
        # never reaches the CFBundle fallback.
        try:
            _qtcore = ctypes.CDLL(qtcore_lib)

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
