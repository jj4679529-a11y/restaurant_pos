import uvicorn
import sys

from app.core.config import get_settings


def main() -> None:
    # Auto-started and manually launched Windows servers share the same mutex.
    # Keep its handle alive for the entire server lifetime (OS releases on exit).
    mutex = None
    if sys.platform == "win32":
        import ctypes
        from ctypes import wintypes
        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel.CreateMutexW.argtypes = [ctypes.c_void_p, wintypes.BOOL, wintypes.LPCWSTR]
        kernel.CreateMutexW.restype = wintypes.HANDLE
        mutex = kernel.CreateMutexW(None, False, "Global\\RestaurantPOS.Server.8000")
        if not mutex:
            raise RuntimeError("Could not acquire RestaurantServer startup mutex")
        if ctypes.get_last_error() == 183:  # ERROR_ALREADY_EXISTS
            return
    settings = get_settings()
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.DEBUG,
    )


if __name__ == "__main__":
    main()
