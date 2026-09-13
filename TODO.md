# TODO

- [ ] System theme detection (dark/light mode, auto-switch based on OS setting)
  - Detection is trivial (read `AppsUseLightTheme` from the registry).
  - The real work is styling every ttk widget class for a dark palette
    (Treeview, Entry, Combobox, LabelFrame, etc.) across every dialog, plus
    darkening the window title bar via the DWM API so it doesn't look
    mismatched. Scope as a proper pass before starting.
- [ ] Add the same system theme detection/dark mode to the Simulator app
      (`tools/fake_vr_signal_simulator.py`) once it's done for the main app.
- [ ] ItemEditorDialog ("Add Device") can outgrow smaller screens - measured
      1143px tall with "Hidden until low" selected (Pop Animation + Nudge
      frames both visible), vs. ~1000-1030px usable height on a 1080p
      display. The dialog is `resizable(False, False)` with no scrollbar, so
      the bottom (including Save) can end up unreachable. Fix by making the
      dialog body scrollable (canvas + scrollbar wrapping the frames, with
      Save/Cancel pinned outside the scroll area) instead of just growing
      taller as more customization gets added.
- [ ] Detect "port already in use" for the overlay server and warn instead of
      (currently) letting it crash uncaught. Scope:
  - Check whether `self.server.start()` can bind the configured port before/
    when starting - both at MainWindow startup and from the manual
    Start/Stop Overlay Server button (`_toggle_server`); neither currently
    guards against a bind failure.
  - On failure, show a small red warning near the Stop Overlay Server
    button/address box, gently flashing, reading something like "Warning:
    Port in use!".
  - Add a button at the end of the address/URL box that switches the
    config to a free port automatically.
  - That button should show a small hover tooltip/info box warning that
    changing the port will break the current OBS Browser Source (since the
    URL OBS already has pointed at it would go stale).
  - Before implementing, actually reproduce today's behavior first (occupy
    the configured port externally, then launch the app / click Start
    Overlay Server) to confirm exactly how it currently fails (suspected:
    an uncaught bind exception crashes the whole app via main.py's generic
    crash handler on startup, or logs an uncaught Tkinter callback
    traceback if triggered later from the toggle button) before designing
    the fix around that real behavior.
- [ ] Add a "Contact Me" link to Jayconius.com in the About dialog
      (`AboutDialog` in `app/gui.py`), alongside the existing GitHub link row.
- [ ] Double-clicking a row in the "Overlay Items" list (`item_tree`) should
      open it for editing, same as selecting it and clicking Edit
      (`MainWindow._edit_selected`). Currently `item_tree` has no double-click
      binding at all.
- [ ] Hide devices that are already used by an existing Overlay Item from the
      device dropdown when adding a NEW Device or Effect
      (`DeviceSelectorMixin._build_device_selector` in `app/gui.py`, shared by
      both `ItemEditorDialog` and `EffectEditorDialog` - currently lists every
      connected device unconditionally, via `self._device_values`/
      `self._device_serials`, with no filtering against already-assigned
      serials). Both dialogs already receive `other_items` (existing
      items/effects to exclude when editing) which can supply the
      already-used serial list. Add a checkbox (e.g. "Show already-added
      devices") to bring the filtered-out devices back into the dropdown when
      the user actually wants to reuse one (e.g. a second Effect on the same
      device).
- [ ] OBS Browser Source doesn't auto-refresh when Device/Effect config
      changes - root-caused: `ITEMS`/`EFFECTS` (position, label, pictures,
      animations, nudge groups, everything except live battery %) are baked
      into the overlay page as a static JSON blob only at page-load time;
      only battery values come from the `/api/status` poll. OBS's Browser
      Source never re-fetches the page on its own, so an edited item needs a
      manual "Refresh cache of current page" today. Fix: expose a small
      "config version" (e.g. config file mtime) from the server, bake the
      version-at-load-time into the page, and have the existing poll loop
      compare it each tick - on mismatch, `location.reload()` the page
      itself. Should self-heal an already-open Browser Source within about
      one poll interval of any save, no OBS interaction needed.
- [ ] Related: closing the app (or the Simulator) leaves the OBS Browser
      Source frozen showing whatever was last rendered forever (e.g. a
      low-battery icon stuck on screen with the app fully closed) - `poll()`
      client-side just silently ignores fetch failures and never clears the
      DOM. Two complementary angles to consider:
  - A graceful signal on clean shutdown (`MainWindow._on_close`): before
    actually stopping the server, briefly serve one last `/api/status`
    response indicating everything's disconnected/hidden, giving the
    already-running poll loop a chance to pick it up and clear itself.
  - A client-side stale-detection fallback (probably the more robust half of
    the fix): if `poll()` fails N consecutive times (a few seconds), treat
    all devices as gone and hide/fade every item, regardless of whether
    shutdown was clean - this is what actually covers a crash, force-kill,
    or power loss, which a graceful-shutdown-only signal can't.

## Deployment (once everything above is done)

- [ ] Write v1.2.0 release notes for the main app (style/format like v1.1.0's).
- [ ] Update README.md and all translated READMEs (de/fr/es/ja) for
      everything new since v1.1.0.
- [ ] Publish the Simulator as its own public GitHub Release: "Oh Fudge, My
      Battery Chat! Demo Simulator v1.0.0" (separate release/tag from the
      main app), with its own release notes.
- [ ] Add a permalink to the Simulator release in README.md's how-to guides
      (and the translated READMEs).
