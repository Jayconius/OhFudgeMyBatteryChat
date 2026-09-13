"""Entry point: launches the configurator GUI (which also runs the overlay
HTTP server that OBS's Browser Source points at)."""
import os
import sys
import traceback


def _crash_log_path():
    from app import paths
    return os.path.join(paths.app_data_dir(), "crash.log")


def _run():
    from app.gui import main
    main()


if __name__ == "__main__":
    try:
        _run()
    except Exception:
        tb = traceback.format_exc()
        try:
            with open(_crash_log_path(), "w", encoding="utf-8") as f:
                f.write(tb)
        except Exception:
            pass
        try:
            import tkinter.messagebox as messagebox
            messagebox.showerror(
                "Oh Fudge, My Battery Chat! - crashed",
                f"Something went wrong:\n\n{tb}\n\nA copy of this was saved to crash.log next to your config.",
            )
        except Exception:
            print(tb, file=sys.stderr)
        sys.exit(1)
