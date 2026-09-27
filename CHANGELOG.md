# Changelog

All notable user-facing changes. The bot checks this file on startup and shows
what's new when an update is available.

## 1.4.3
- One-click in-app update (no git needed): the "Update Available" popup can now
  download and apply the update for you. Your settings, accounts and runtime are
  kept — just reopen the app afterwards. ("Open GitHub" is still there for the
  manual route.)
- The popup also shows a "What's new" changelog so you can see what changed
  before updating.

## 1.4.2
- MEmu hang auto-recovery: a frozen emulator (screencap timeouts → "device
  offline") is now hard-restarted (memuc stop → start of that instance) instead
  of getting stuck retrying; adb calls have timeouts so recovery can't hang.
- Storage full-detection coordinates and colors moved to `config/farming.json`
  → `storage_detect` (HUD regions, dark-bar geometry, purple color thresholds).
  You can re-align them yourself if a game update shifts the HUD — no code edit,
  no image/template to re-shoot.

## 1.4.1
- Fixed battle-end detection after the CoC UI update (the "Return Home" button
  moved — template re-shot); the bot detects the end of battle again.
- Fixed the speed-up "1x" button position (moved after the patch) — battles
  speed up again.
- Deploy guard: if the bot ends up back on the home base (battle already over),
  it stops blindly tapping troops (detected via the in-battle UI).
- Event 3★ reward: on the end-of-battle resource screen the bot picks Dark
  Elixir (rightmost). Toggle in `config/farming.json` → `event_reward`.
- Native Dragon/EDragon attacks use stable static deploy geometry (zoom is
  normalized once per cycle).

## 1.4.0
- Multi-village restored under multi-bot workers; more robust MEmu detection.
</content>
