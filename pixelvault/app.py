import sys
import argparse
import logging

from pixelvault.config import APP_NAME, APP_VERSION, DATA_DIR


def setup_logging(debug: bool = False):
    level = logging.DEBUG if debug else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )


def run_gui(dev: bool = False):
    from PySide6.QtWidgets import QApplication
    from PySide6.QtCore import Qt

    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setApplicationVersion(APP_VERSION)
    app.setOrganizationName(APP_NAME)

    if dev:
        setup_logging(debug=True)
    else:
        setup_logging(debug=False)

    DATA_DIR.mkdir(parents=True, exist_ok=True)

    from pixelvault.database.connection import initialize_database
    initialize_database()

    from pixelvault.gui.main_window import MainWindow
    window = MainWindow()
    window.show()

    sys.exit(app.exec())


def run_scan(args):
    setup_logging()
    from pixelvault.database.connection import initialize_database
    initialize_database()

    from pixelvault.core.scanner import ScannerOrchestrator
    scanner = ScannerOrchestrator()

    if args.force:
        from pixelvault.database.dao import LibraryDAO
        lib_dao = LibraryDAO()
        libs = lib_dao.get_all()
        for lib in libs:
            if args.path and lib.directory_path == args.path:
                ids = scanner.scan_library(lib.id, force=True)
                print(f"Force scan complete: {len(ids)} new assets in {lib.directory_path}")
                return
        if args.path:
            lib_id = scanner.add_library(args.path)
            ids = scanner.scan_library(lib_id, force=True)
            print(f"Force scan complete: {len(ids)} new assets")
        else:
            for lib in libs:
                ids = scanner.scan_library(lib.id, force=True)
                print(f"Force scan complete: {len(ids)} new assets in {lib.directory_path}")
    else:
        if args.path:
            lib_id = scanner.add_library(args.path)
            ids = scanner.scan_library(lib_id)
            print(f"Scan complete: {len(ids)} new assets")
        else:
            ids = scanner.scan_all_libraries()
            print(f"Scan all complete: {len(ids)} new assets")


def run_db_upgrade(args):
    setup_logging()
    from pixelvault.database.connection import initialize_database
    initialize_database()
    print("Database initialized successfully")


def main():
    parser = argparse.ArgumentParser(prog=APP_NAME, description="Local Multimedia Asset Management & Intelligent Search Hub")
    parser.add_argument("--version", action="version", version=f"{APP_NAME} {APP_VERSION}")
    subparsers = parser.add_subparsers(dest="command")

    run_parser = subparsers.add_parser("run", help="Launch the GUI application")
    run_parser.add_argument("--dev", action="store_true", help="Development mode with debug logging")

    scan_parser = subparsers.add_parser("scan", help="Scan media libraries")
    scan_parser.add_argument("path", nargs="?", help="Directory path to scan")
    scan_parser.add_argument("--force", action="store_true", help="Force re-scan")

    db_parser = subparsers.add_parser("db", help="Database management")
    db_sub = db_parser.add_subparsers(dest="db_command")
    upgrade_parser = db_sub.add_parser("upgrade", help="Initialize/upgrade database")

    args = parser.parse_args()

    if args.command == "run":
        run_gui(dev=getattr(args, "dev", False))
    elif args.command == "scan":
        run_scan(args)
    elif args.command == "db" and args.db_command == "upgrade":
        run_db_upgrade(args)
    else:
        run_gui()


if __name__ == "__main__":
    main()
