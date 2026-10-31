"""Command-line interface for PyFFB Studio."""

from __future__ import annotations

import argparse
import json
import os
import platform
import sys
import time
from pathlib import Path
from typing import Any, Iterable, Sequence

from . import __version__
from .backends import BackendError, make_backend
from .config import (
    AppConfig,
    ConfigStore,
    ProfileLibrary,
    export_profile,
    import_profile,
)
from .controller import SafetyPolicy, WheelController
from .gamewatch import GameSession, process_snapshot
from .logging_setup import setup_logging
from .models import FIELD_LABELS, ModelError, WheelSettings, profile_diff
from .presets import GENERIC_PROFILE_ID

BACKEND_CHOICES = ("openffboard", "simulator")


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="pyffb",
        description=(
            "PyFFB Studio - clean-room FFB wheel manager. "
            "Configures OpenFFBoard firmware and switches game profiles; "
            "real-time FFB remains in the wheel firmware."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  pyffb gui --simulate\n"
            "  pyffb devices\n"
            "  pyffb apply --port COM5 --profile acc\n"
            "  pyffb watch --port COM5\n"
            "  pyffb profiles list\n"
        ),
    )
    parser.add_argument("--config-dir", type=Path, help="override the application data directory")
    parser.add_argument("-v", "--verbose", action="store_true", help="debug logging")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    sub = parser.add_subparsers(dest="command")

    gui = sub.add_parser("gui", help="open the desktop application")
    gui.add_argument("--simulate", action="store_true", help="start against the built-in simulator")
    gui.add_argument("--profile", help="select a profile on startup")

    devices = sub.add_parser("devices", help="list candidate serial ports")
    devices.add_argument("--backend", choices=BACKEND_CHOICES, default=None)
    devices.add_argument("--json", action="store_true")

    info = sub.add_parser("info", help="read device identity, settings and telemetry")
    _connection_args(info)
    info.add_argument("--json", action="store_true")

    apply = sub.add_parser("apply", help="apply a profile to a connected wheel")
    _connection_args(apply)
    apply.add_argument("--profile", required=True)
    apply.add_argument("--persist", action="store_true", help="save settings to wheel flash")
    apply.add_argument(
        "--no-rotation",
        action="store_true",
        help="do not change wheel range or invert direction",
    )
    apply.add_argument("--dry-run", action="store_true", help="show differences only")

    profiles = sub.add_parser("profiles", help="list, inspect, import or export profiles")
    profile_sub = profiles.add_subparsers(dest="profile_command")
    p_list = profile_sub.add_parser("list", help="list built-in and custom profiles")
    p_list.add_argument("--json", action="store_true")
    p_list.add_argument("--grep", help="filter by id, name or game")
    p_show = profile_sub.add_parser("show", help="print a profile as JSON")
    p_show.add_argument("profile_id")
    p_export = profile_sub.add_parser("export", help="export a profile")
    p_export.add_argument("profile_id")
    p_export.add_argument("path", type=Path)
    p_import = profile_sub.add_parser("import", help="import a profile into user profiles")
    p_import.add_argument("path", type=Path)
    p_delete = profile_sub.add_parser("delete", help="delete a custom profile")
    p_delete.add_argument("profile_id")

    watch = sub.add_parser("watch", help="auto-apply profiles while games start and exit")
    _connection_args(watch)
    watch.add_argument("--interval", type=float, default=2.0, help="poll interval in seconds")
    watch.add_argument("--persist", action="store_true", help="persist profile changes")

    simulate = sub.add_parser("simulate", help="run a headless simulator and print telemetry")
    simulate.add_argument("--seconds", type=float, default=5.0)
    simulate.add_argument("--interval", type=float, default=0.25)
    simulate.add_argument("--profile", default=GENERIC_PROFILE_ID)

    sub.add_parser("doctor", help="check dependencies, paths and profiles")

    config = sub.add_parser("config", help="inspect or reset local configuration")
    config_sub = config.add_subparsers(dest="config_command")
    config_sub.add_parser("path", help="print the config directory")
    config_sub.add_parser("show", help="print the current configuration")
    reset = config_sub.add_parser("reset", help="reset configuration to defaults")
    reset.add_argument("--yes", action="store_true", help="confirm reset")

    return parser


def _connection_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--port", help="serial port, e.g. COM5 or /dev/ttyACM0")
    parser.add_argument("--backend", choices=BACKEND_CHOICES, default=None)


def _load(args: argparse.Namespace) -> tuple[ConfigStore, AppConfig, ProfileLibrary]:
    store = ConfigStore(Path(args.config_dir) if args.config_dir else None)
    config = store.load()
    library = ProfileLibrary(config.custom_profiles)
    return store, config, library


def _backend_key(args: argparse.Namespace, config: AppConfig) -> str:
    return getattr(args, "backend", None) or config.backend_key


def _port(args: argparse.Namespace, config: AppConfig, backend_key: str) -> str:
    if backend_key == "simulator":
        return "simulator"
    port = getattr(args, "port", None) or config.port
    if not port:
        raise BackendError("no serial port selected; run 'pyffb devices' and pass --port")
    return port


def _controller(
    config: AppConfig,
    store: ConfigStore,
    backend_key: str,
):
    backend = make_backend(backend_key)
    policy = SafetyPolicy(max_power_pct=config.safety_max_power_pct)
    return WheelController(backend, policy), store


def _print_table(headers: Sequence[str], rows: Iterable[Sequence[Any]]) -> None:
    data = [[str(cell) for cell in row] for row in rows]
    widths = [len(header) for header in headers]
    for row in data:
        for index, cell in enumerate(row):
            widths[index] = max(widths[index], len(cell))
    pattern = "  ".join("{:<" + str(width) + "}" for width in widths)
    print(pattern.format(*headers))
    print("  ".join("-" * width for width in widths))
    for row in data:
        print(pattern.format(*row))


def _settings_rows(settings: WheelSettings) -> list[tuple[str, Any]]:
    labels = settings.to_dict()
    return [(FIELD_LABELS.get(key, key), value) for key, value in labels.items()]


def _report_text(report) -> str:
    if report.errors:
        return "\n".join(f"ERROR: {error}" for error in report.errors)
    parts: list[str] = []
    if report.fields:
        parts.append(
            "Applied: " + ", ".join(FIELD_LABELS.get(field, field) for field in report.fields)
        )
    else:
        parts.append("No changes were necessary.")
    if report.skipped:
        parts.append(
            "Skipped: " + ", ".join(FIELD_LABELS.get(field, field) for field in report.skipped)
        )
    if report.persisted:
        parts.append("Saved to wheel flash.")
    if report.rolled_back:
        parts.append("Changes were rolled back.")
    for warning in report.warnings:
        parts.append(f"Warning: {warning}")
    return "\n".join(parts)


def _cmd_gui(args: argparse.Namespace) -> int:
    store, config, library = _load(args)
    if args.simulate:
        config = AppConfig.from_dict(
            {
                **config.to_dict(),
                "backend_key": "simulator",
                "port": "simulator",
                "last_profile_id": args.profile or config.last_profile_id,
            }
        )
    elif args.profile:
        if not library.has(args.profile):
            raise BackendError(f"unknown profile: {args.profile}")
        config = AppConfig.from_dict({**config.to_dict(), "last_profile_id": args.profile})
    try:
        from .gui.app import run_gui
    except Exception as exc:  # missing Tk/display is platform-specific
        print(f"Desktop UI is unavailable: {exc}", file=sys.stderr)
        print("Run 'pyffb doctor' and install Tkinter; the simulator can also be used via the CLI.", file=sys.stderr)
        return 2

    return run_gui(store=store, config=config, library=library)


def _cmd_devices(args: argparse.Namespace) -> int:
    _, config, _ = _load(args)
    keys = [args.backend] if args.backend else ["openffboard", "simulator"]
    descriptors = []
    for key in keys:
        backend = make_backend(key)
        descriptors.extend(backend.list_devices())
    if args.json:
        print(
            json.dumps(
                [
                    {
                        "key": item.key,
                        "port": item.port,
                        "description": item.description,
                        "display_name": item.display_name,
                        "hwid": item.hwid,
                        "simulated": item.simulated,
                    }
                    for item in descriptors
                ],
                indent=2,
            )
        )
        return 0
    if not descriptors:
        print("No serial ports found. Install pyserial and check the USB cable/driver.")
        print("Use '--backend simulator' for the no-hardware demo.")
        return 0
    _print_table(
        ("Backend", "Port", "Description", "Hardware ID"),
        ((d.key, d.port, d.display_name, d.hwid) for d in descriptors),
    )
    return 0


def _cmd_info(args: argparse.Namespace) -> int:
    store, config, _ = _load(args)
    key = _backend_key(args, config)
    port = _port(args, config, key)
    controller, _ = _controller(config, store, key)
    info = controller.connect(port)
    try:
        read = controller.read_settings()
        telemetry = controller.read_telemetry(read.settings.rotation_deg)
        if args.json:
            print(
                json.dumps(
                    {
                        "device": {
                            "backend": info.backend_key,
                            "name": info.display_name,
                            "port": info.port,
                            "firmware": info.firmware,
                            "hardware": info.hardware,
                        },
                        "settings": read.settings.to_dict(),
                        "telemetry": {
                            "position_deg": telemetry.position_deg,
                            "torque_pct": telemetry.torque_pct,
                            "speed_dps": telemetry.speed_dps,
                            "ffb_active": telemetry.ffb_active,
                            "supply_voltage": telemetry.supply_voltage,
                            "temperature_c": telemetry.temperature_c,
                        },
                        "missing_fields": list(read.missing),
                    },
                    indent=2,
                )
            )
        else:
            print(f"{info.display_name} on {info.port}")
            print(f"Firmware: {info.firmware or 'unknown'}  Hardware: {info.hardware or 'unknown'}")
            print()
            _print_table(("Setting", "Value"), _settings_rows(read.settings))
            print()
            print(
                "Telemetry: "
                f"position={_fmt(telemetry.position_deg, ' deg')} "
                f"torque={_fmt(telemetry.torque_pct, '%')} "
                f"speed={_fmt(telemetry.speed_dps, ' deg/s')} "
                f"FFB={telemetry.ffb_active} "
                f"voltage={_fmt(telemetry.supply_voltage, ' V')} "
                f"temp={_fmt(telemetry.temperature_c, ' C')}"
            )
            if read.missing:
                print("Unread fields: " + ", ".join(read.missing))
        return 0
    finally:
        controller.disconnect()


def _fmt(value: Any, suffix: str = "") -> str:
    if value is None:
        return "n/a"
    if isinstance(value, bool):
        return "on" if value else "off"
    if isinstance(value, float):
        return f"{value:.1f}{suffix}"
    return f"{value}{suffix}"


def _cmd_apply(args: argparse.Namespace) -> int:
    store, config, library = _load(args)
    profile = library.get(args.profile)
    key = _backend_key(args, config)
    port = _port(args, config, key)
    controller, _ = _controller(config, store, key)
    controller.connect(port)
    try:
        if args.dry_run:
            read = controller.read_settings()
            changed = profile_diff(read.settings, profile.settings)
            if not changed:
                print("No differences between the wheel and the profile.")
            else:
                print("Dry run; no writes performed. Fields that would change:")
                for field in changed:
                    print(
                        f"  {FIELD_LABELS.get(field, field)}: "
                        f"{getattr(read.settings, field)} -> {getattr(profile.settings, field)}"
                    )
            return 0
        report = controller.apply_profile(
            profile,
            include_geometry=not args.no_rotation,
            persist=args.persist,
        )
        print(_report_text(report))
        return 0 if report.ok else 1
    finally:
        controller.disconnect()


def _cmd_profiles(args: argparse.Namespace) -> int:
    store, config, library = _load(args)
    command = args.profile_command
    if command in {None, "list"}:
        profiles = list(library.all())
        if getattr(args, "grep", None):
            needle = args.grep.lower()
            profiles = [
                p
                for p in profiles
                if needle in p.id.lower()
                or needle in p.name.lower()
                or needle in p.game.lower()
            ]
        if getattr(args, "json", False):
            print(json.dumps([profile.to_dict() for profile in profiles], indent=2))
            return 0
        _print_table(
            ("ID", "Name", "Game", "Executables", "Custom"),
            (
                (
                    p.id,
                    p.name,
                    p.game,
                    ", ".join(p.exe_names) or "-",
                    "yes" if not p.builtin else "",
                )
                for p in profiles
            ),
        )
        return 0
    if command == "show":
        print(json.dumps(library.get(args.profile_id).to_dict(), indent=2))
        return 0
    if command == "export":
        profile = library.get(args.profile_id)
        export_profile(profile, args.path)
        print(f"Exported {profile.id} to {args.path}")
        return 0
    if command == "import":
        profile = import_profile(args.path)
        library.add_custom(profile)
        config = AppConfig.from_dict(
            {**config.to_dict(), "custom_profiles": [p.to_dict() for p in library.custom()]}
        )
        store.save(config)
        print(f"Imported {profile.id} ({profile.name})")
        return 0
    if command == "delete":
        library.remove_custom(args.profile_id)
        config = AppConfig.from_dict(
            {**config.to_dict(), "custom_profiles": [p.to_dict() for p in library.custom()]}
        )
        store.save(config)
        print(f"Deleted {args.profile_id}")
        return 0
    return 2


def _cmd_watch(args: argparse.Namespace) -> int:
    store, config, library = _load(args)
    key = _backend_key(args, config)
    port = _port(args, config, key)
    controller, _ = _controller(config, store, key)
    controller.connect(port)
    session = GameSession(library, config.desktop_profile_id)
    print(f"Watching for games on {port}. Ctrl+C to stop.")
    try:
        while True:
            change = session.update(process_snapshot())
            if change:
                profile = library.get(change.profile_id)
                print(
                    f"[{time.strftime('%H:%M:%S')}] {change.reason}: "
                    f"{profile.name} ({profile.id})"
                )
                report = controller.apply_profile(
                    profile,
                    include_geometry=config.auto_apply_geometry,
                    persist=args.persist,
                )
                if not report.ok:
                    print(_report_text(report), file=sys.stderr)
            time.sleep(max(0.5, args.interval))
    except KeyboardInterrupt:
        return 0
    finally:
        controller.disconnect()


def _cmd_simulate(args: argparse.Namespace) -> int:
    store, config, library = _load(args)
    profile = library.get(args.profile)
    backend = make_backend("simulator")
    controller = WheelController(backend, SafetyPolicy(config.safety_max_power_pct))
    controller.connect("simulator")
    report = controller.apply_profile(profile, include_geometry=True)
    print(_report_text(report))
    deadline = time.monotonic() + max(0.0, args.seconds)
    try:
        while time.monotonic() < deadline:
            t = controller.read_telemetry(profile.settings.rotation_deg)
            print(
                f"pos={_fmt(t.position_deg, ' deg'):>10}  "
                f"torque={_fmt(t.torque_pct, '%'):>8}  "
                f"speed={_fmt(t.speed_dps, ' deg/s'):>12}  ffb={'on' if t.ffb_active else 'off'}"
            )
            time.sleep(max(0.05, args.interval))
    except KeyboardInterrupt:
        pass
    finally:
        controller.disconnect()
    return 0


def _cmd_doctor(args: argparse.Namespace) -> int:
    store, config, library = _load(args)
    print(f"PyFFB Studio {__version__}")
    print(f"Python: {sys.version.split()[0]} ({sys.executable})")
    print(f"Platform: {platform.platform()}")
    print(f"Config: {store.base_dir}")
    issues = 0
    try:
        import serial  # noqa: F401

        serial_status = "ok"
    except ImportError:
        serial_status = "MISSING - pip install pyserial"
        issues += 1
    try:
        import psutil  # noqa: F401

        psutil_status = "ok"
    except ImportError:
        psutil_status = "missing (tasklist fallback will be used)"
    try:
        import tkinter  # noqa: F401

        tk_status = "ok"
    except Exception as exc:  # pragma: no cover - platform specific
        tk_status = f"unavailable: {exc}"
        issues += 1
    print(f"pyserial: {serial_status}")
    print(f"psutil: {psutil_status}")
    print(f"tkinter: {tk_status}")
    try:
        store.ensure_dirs()
        test = store.base_dir / ".write-test"
        test.write_text("ok", encoding="utf-8")
        test.unlink()
        print("Config directory: writable")
    except OSError as exc:
        print(f"Config directory: NOT WRITABLE ({exc})")
        issues += 1
    print(f"Built-in profiles: {len(library.builtins())}")
    print(f"Custom profiles: {len(library.custom())}")
    for warning in store.warnings:
        print(f"Config warning: {warning}")
    print(f"Safety power cap: {config.safety_max_power_pct}%")
    ports = make_backend("openffboard").list_devices()
    print(f"Serial ports: {len(ports)}")
    for port in ports:
        print(f"  {port.port}: {port.display_name}")
    print("Simulator: always available")
    return 1 if issues else 0


def _cmd_config(args: argparse.Namespace) -> int:
    store, config, _library = _load(args)
    command = args.config_command
    if command == "path":
        print(store.base_dir)
        return 0
    if command == "show":
        print(json.dumps(config.to_dict(), indent=2))
        return 0
    if command == "reset":
        if not args.yes:
            print("Refusing to reset without --yes", file=sys.stderr)
            return 2
        store.save(AppConfig())
        print("Configuration reset.")
        return 0
    print(store.base_dir)
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    parser = _parser()
    args = parser.parse_args(argv)
    if args.config_dir:
        os.environ["PYFFB_CONFIG_DIR"] = str(args.config_dir)
    setup_logging(verbose=getattr(args, "verbose", False), log_dir=None)
    if args.command is None:
        args = argparse.Namespace(
            config_dir=args.config_dir,
            verbose=args.verbose,
            command="gui",
            simulate=False,
            profile=None,
        )
    try:
        if args.command == "gui":
            return _cmd_gui(args)
        if args.command == "devices":
            return _cmd_devices(args)
        if args.command == "info":
            return _cmd_info(args)
        if args.command == "apply":
            return _cmd_apply(args)
        if args.command == "profiles":
            return _cmd_profiles(args)
        if args.command == "watch":
            return _cmd_watch(args)
        if args.command == "simulate":
            return _cmd_simulate(args)
        if args.command == "doctor":
            return _cmd_doctor(args)
        if args.command == "config":
            return _cmd_config(args)
    except (BackendError, KeyError, ModelError, OSError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    return 2


def gui_entry() -> None:
    raise SystemExit(main(["gui"]))


if __name__ == "__main__":
    raise SystemExit(main())
