# Error Handling

## If `kmi proxy` fails
- Ensure port free or install `lsof`.
- Use `kmi proxy-restart --yes`.

## If `kmi doctor` shows FAIL
- Read the `fix:` line and apply it.
- Re‑run doctor.

## If trace is empty
- Use `kmi kimi` wrapper.
- Confirm `KIMI_BASE_URL`.

