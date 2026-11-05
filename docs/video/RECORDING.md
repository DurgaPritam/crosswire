# Recording guide

## Before you start
- **Do Not Disturb** on (Control Centre → Focus). Quit chat apps, mail and anything that can pop up.
- Display at 1920×1080, or a scaled mode where the Console window is exactly 1920×1080. The Console scales its frame
  to the window. Check that the top bar and timeline are fully visible.
- `just console-replay` (no Switch needed). Open http://127.0.0.1:7300/ in a clean browser profile (no extensions,
  bookmarks bar hidden), full screen.
- Press **P** for presentation mode. Replay speed: 1× for the beats you narrate, 2× for waiting parts. The timeline
  label shows the speed, so it's always visible on screen.
- For the picture-in-picture cuts, have Mattermost open in a second window, already scrolled to the run's posts
  (Sam's report, an approval, "confirm root cause"). Record it separately; it's easier to place in the edit.

## Recording
- **macOS:** ⌘⇧5 → "Record Selected Portion", select the browser window, Options → no microphone (record the voice
  separately), "Show Mouse Clicks" off.
- **OBS (better for 60 fps):** Base and Output resolution 1920×1080, 60 fps; a macOS Screen Capture source for the
  browser window; Recording → MP4 (or MKV then remux), encoder Apple VT H.264, bitrate ~12,000 kbps.
- Record each beat as its own clip. Use the replay controls (pause, seek) to set up the next beat.

## Voice
- A quiet room with soft furnishings. Mic 10–15 cm away, slightly off-axis to avoid pops.
- Record the whole script in one take per section and leave a second of silence between lines.
- Read the numbers off the finale of the replayed run first, so the voiceover matches the screen.
- Level: peaks around −6 dB, nothing clipping. Light noise reduction only.

## Edit and export
- Cut to SCRIPT.md (2:45 target, 3:00 hard cap). PiP Mattermost at about 30% width, bottom right, with a 16 px margin.
- Export H.264 MP4, 1920×1080, 60 fps (30 is fine if the source is 30), AAC 48 kHz stereo.
- Upload to YouTube as **Unlisted**. Title "Crosswire: two companies debug a bug without sharing code (Flip the
  Switch)". Add the repo link in the description. Paste the URL into the README.
