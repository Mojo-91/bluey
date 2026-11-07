# Bluey

A blue dome-face companion. Your Android phone is the face; the Bluey app on your Windows PC is the brain.
Hold the phone screen, talk, let go. His eyes follow your mouse, he points at things on screen, opens apps,
types, researches, and never speaks out loud.

## Install (no Python, no Android Studio)
1. Put this folder on GitHub once (free). GitHub then builds `Bluey.exe` (PC) and `Bluey.apk` (phone) for you.
2. Download both from the repo's **Releases** page.
3. PC: double-click `Bluey.exe`. Paste your Anthropic API key in its window.
4. Phone: open `Bluey.apk`, install, open Bluey (same Wi-Fi as the PC).
5. Type the 6-digit code from the PC window into the phone. Done. You only pair once.

## How it works
    Android phone (face, hold-to-talk)  <-- Wi-Fi, 6-digit pairing code -->  Windows app (window + tray)
                                                                               |- Claude API: computer use + web search
                                                                               |- Pointer overlay, research card
Nothing on the phone can do anything until it has sent the right code. 5 wrong codes lock pairing for a minute.
"New code" in the PC window disconnects the phone and needs a re-pair.

## Face states (phone)
idle: eye icon, heavy lids. listening: thick blue border (thicker while held). thinking: purple. researching: amber.
replying: pink. pointing: green. sleeping: closed eyes. Borders are solid and follow the phone's screen corners.

## Wire format (one JSON object per line, TCP :47474)
phone > PC: `{"t":"hello","code":"123456"}` first, then `{"t":"wake"}`, `{"t":"ask","text":"..."}`
PC > phone: `{"t":"ok"}` or `{"t":"denied"}`, then `{"t":"state","s":"..."}`, `{"t":"look","x":0.5,"y":0.5}`,
`{"t":"say","text":"..."}`, `{"t":"report","title":"...","text":"...","sources":[["title","url"]]}`

## Notes
- Not run on a real phone or a real Windows PC by me. The cloud build is untested, so the first build may need a small fix.
- `Windows/bluey/agent.py` has the model and computer-use tool version as constants. Check them against the current docs.
- He controls your real mouse and keyboard. "Pause computer control" in the PC window stops it. Admin windows can't be controlled unless Bluey runs as admin.
- Dev mode without the cloud build: `Windows/run.bat` and open `Android/` in Android Studio.
