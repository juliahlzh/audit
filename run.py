import importlib
import sys

from app.config import HOST, PORT, RELOAD


REQUIRED_MODULES = [
    "fastapi",
    "uvicorn",
    "jinja2",
    "sqlalchemy",
    "passlib",
    "pytesseract",
    "PIL",
    "pypdf",
    "pandas",
    "openpyxl",
    "reportlab",
]


def check_modules():
    missing = []
    for module_name in REQUIRED_MODULES:
        try:
            importlib.import_module(module_name)
        except Exception:
            missing.append(module_name)
    return missing


def main():
    missing = check_modules()
    if missing:
        print("FEWS belum bisa dijalankan karena dependency berikut belum terpasang:")
        for module_name in missing:
            print(f"- {module_name}")
        print("")
        print("Jalankan salah satu perintah berikut:")
        print(r"1. .\setup_local.ps1")
        print(r"2. pip install -r requirements.txt")
        sys.exit(1)

    import uvicorn

    print(f"Menjalankan FEWS di http://{HOST}:{PORT}")
    uvicorn.run("app.main:app", host=HOST, port=PORT, reload=RELOAD)


if __name__ == "__main__":
    main()
