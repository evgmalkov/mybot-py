# Changelog

All notable user-facing changes. The bot checks this file on startup and shows
what's new when an update is available.

## 1.4.7
- Re-cut the Electro Dragon troop icon at the new army-window scale so the
  pre-attack army check works for Electro Dragon armies too (same UI-shrink fix
  as the dragon/balloon icons in 1.4.6).

## 1.4.6
- Fixed the pre-attack army check and auto-retraining after a game UI update:
  the housing counter was misread (the red "!" warning next to it added a digit,
  e.g. 352/352 → 352/3521) so training was skipped and the bot attacked with the
  wrong army. Also re-cut the dragon/balloon troop icons (the army window shrank
  them) so the composition check detects them again.

## 1.4.5
- Fixed the in-app updater's "Please wait" dialog getting stuck on screen after
  an update was applied; it now closes cleanly and shows the restart prompt.

## 1.4.4
- Fixed the battle speed-up "1x" button (a game update moved it down); battles
  speed up again. Its position/threshold/template now live in
  `config/antiban.json` (`speed_button_*`) so you can re-align it without code if
  the game moves it again.

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
