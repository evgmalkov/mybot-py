; screenshot_memu_run.ahk  (AutoHotkey v2 syntax)
; --------------------------------------------------------------
; Run this script (double‑click or call from CLI) and it will:
;   • activate the first visible MEmu window
;   • send Alt+F3 to trigger a screenshot
;   • exit immediately
;
; No hotkeys, no waiting—just run → screenshot.
; --------------------------------------------------------------

#Requires AutoHotkey v2.0
#SingleInstance Force

; Try to bring MEmu to the foreground
if WinExist("ahk_exe MEmu.exe")
    WinActivate("ahk_exe MEmu.exe")
else if WinExist("MEmu")
    WinActivate("MEmu")
else {
    MsgBox("MEmu window not found!", "Error", "Iconx")
    ExitApp
}

; Send Alt+F3 (MEmu's screenshot hot‑key)
Send("!{F3}")

ExitApp
