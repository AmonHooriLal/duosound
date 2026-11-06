# DuoSound design system

The DuoSound window is a **Windows desktop tool used in a dimmed room next to a playing movie**. The look is a dark,
warm "movie night" surface that stays calm and out of the way. The orange accent appears only on the primary action,
the current selection and live state. Mode: *Operate*. People must finish one task (start sharing sound) without
reading anything, so familiar controls win over novelty.

**Source of truth:** `duosound/ui/theme.py`. Every colour, font, size, icon and sentence below lives there. Views never
hard-code any of them, so a redesign touches only that one file.

## Colour
| Token | Hex | Use |
|---|---|---|
| `BG` | `#16120F` | window background, header, footer |
| `SURFACE` | `#211B16` | sections (Sound source, Headphones), action bar, Help/About cards |
| `SURFACE_2` | `#2C241D` | inputs, secondary buttons, slider troughs, hover |
| `SURFACE_3` | `#3A3027` | pressed / selected (Help topic in view) |
| `LINE` | `#3D3229` | hairlines |
| `TEXT` | `#F4EADF` | primary text |
| `TEXT_2` | `#C9B8A8` | secondary text, icons |
| `TEXT_3` | `#A08F80` | captions, hints (≥ 4.5:1 on `SURFACE`) |
| `ACCENT` | `#F28C2E` | Start/Stop, checkbox ticks, links, Donate heart, meter |
| `ON_ACCENT` | `#1B1007` | text on the orange button (white on orange fails contrast) |
| `OK` / `WARN` / `BAD` / `INFO` | `#6CCB94` / `#F2BE55` / `#F27A63` / `#8DB8F0` | live state and banners, always paired with words |

Rules: the accent never decorates. Status is never conveyed by colour alone: a status dot always has a label
("Playing · 62 ms", "Reconnecting…"). The title bar follows the window colours (DWM caption colour on Windows 11).

## Type
One family: **Segoe UI** (the Windows UI face), on a tight scale:
title 15 bold · section 11 bold · body 10 · body bold 10 · small 9 · primary button 11 bold. The log uses Cascadia Mono 9 (data only).
Fixed sizes in points, so Windows display scaling enlarges everything evenly.

## Spacing and size
4 / 8 / 12 / 16 / 24 px steps (`GAP_XS…GAP_XL`), multiplied by display scaling (`px()`). The window is 980×720 by
default, 760×520 at minimum, and never larger than the screen. Sections have 16 px side padding and 12 px between them.

## Layout (main page, top to bottom)
1. **Header:** app icon, "DuoSound", tagline. **Help** on the right (it becomes **Back** on other pages).
2. **Sound source:** dropdown + Refresh, one plain-words hint, problem banners, and a collapsed **Options** (auto-switch
   output, mute speakers, Windows sound settings).
3. **Headphones:** a scrolling list. Each row has a checkbox, a type icon, the product name with its type and live status
   underneath, Delay (0–1000 ms), Volume (0–150 %) and Test. When nothing is connected, an empty state teaches the next
   step (Bluetooth settings, Refresh).
4. **Banners:** inline messages with a "How to fix" link into Help. Confirmations (calibrate, loud speakers) are banners
   with buttons, never popups.
5. **Action bar** (always visible): **Start/Stop** (the only orange button), Calibrate, Unmute speakers (only while
   DuoSound has muted them), status text, and the Sound-in meter.
6. **Footer:** "Made by Amon Lal", **Donate**, Log toggle, version.

Other pages replace the main page in the same window: **Help** (topic list, topic text, Copy diagnostics / Open log
folder / Bluetooth settings) and **Donate & about** (credit, UPI ID + Copy, the QR at 220–300 px so a phone can scan it).

## Components
- **Buttons:** Primary (orange, dark text), default (`SURFACE_2`), Ghost (text + icon, for header and footer), Link
  (orange small text), Nav (Help topics). Every button has hover, pressed, disabled and focus (orange border) states.
- **Icons:** drawn with PIL at 4× and downscaled, in one stroke weight. The set is headphones, bluetooth, plug, speaker
  (on/off), help, heart, back, play, stop, target, refresh, folder, copy, chevrons, warning, check, cross and dot.
  No emoji or Unicode symbols are used as icons.
- **Sliders** ignore the mouse wheel, so scrolling the list never changes a delay by accident.
- **Scrollbar:** a thin bar with no arrow buttons, shown only when the list overflows.

## Scenery (planned, 2026-11-06)
Amon's direction: a poster-like illustrated landscape behind the UI, which follows the theme.
- **Dark:** a moonlit night with a speckled moon and soft glow, stars, and a small house with warm lit windows.
- **Light:** a sunny day with a rayed sun and drifting clouds.
- **Both:** distant hills; a lake with a shimmering moon/sun path; Italian cypresses and round two-tone trees (the side facing the light is lighter); a grass meadow.
- **Motion:** trees and grass sway in a gusting wind that rolls left to right, the water glints shimmer and the stars twinkle. A theme switch crossfades.
- **Calm:** no motion when Windows animations are off; the scene pauses when minimised; it uses about 13 % of one core at 15 fps.
- **Palettes:** the scene has its own palettes (`SCENES` in `scenery.py`), so the UI tokens stay unchanged.
- **Panels:** solid in tkinter. Frosted glass (blur + 55–65 % surface + a 1 px light border) is only possible with Flet. That decision is open; see CONTEXT.md.
- **Review fixes:** the open items from the critique (check-mark checkbox, one-line source, Delay behind "Adjust sync", ellipsized names) apply whichever toolkit is chosen.

## Words
Plain words (PRODUCT.md principle 3): "Sound source", "Headphones", "Delay", "Test", "Waiting for sound. Start the
movie." No "loopback", "A2DP" or "endpoint" in the window. Every problem names the fix or links to it.

## Direction for the Flet window (2026-11-06, frontend-design pass)
Replaces the colour and type sections above once the Flet UI ships. The world is the moonlit-coast travel poster Amon shared.
- **Colour (dark):** night ink `#0F1B33` (base and glass tint), moon cream `#F2E6C8` (text), lamplight amber `#F4B03E` (Start, live state), vermilion `#E5572F` (Stop, errors), meadow `#8CCB8A` (success).
- **Colour (light):** white glass over the sunny sky, ink `#14223F` text (not black), the same amber, `#C2411F` for alerts and `#2F7A44` for success.
- **Type:**
  - **Oswald** 600, only for the "DuoSound" title, set directly on the sky like a poster headline.
  - **Atkinson Hyperlegible** for everything else (made for low-light legibility), on a 12 / 14 / 16 / 20 scale. Both are bundled (SIL OFL).
- **Layout:**
  - The title and the one-line source ("Copying sound from … · Change") sit on the scene with no panel.
  - Only two glass surfaces: the headphone list (rows split by hairlines) and the action bar. Left-aligned throughout.
  - Radii: 18 for the surfaces, 10 for controls.
- **Restraint:**
  - The scenery is the one bold element.
  - No entrance animations; motion only answers an action (150–220 ms).
  - Sentence case, no all-caps labels, no eyebrows, no "→".
- **Why not the earlier palette:** warm near-black + orange is a generic "dark + one accent" look, and cream + terracotta is the most common generic light theme. The new colours come from the scene itself.


## Flet UI (duosound/ui_flet, chosen 2026-11-06; tkinter in duosound/ui stays as the fallback)
Tokens live in `duosound/ui_flet/tokens.py`, words in `words.py`, the scene in `scenery.py`. This section replaces the tkinter palette above for the Flet window.
- **Colour:** dark = night ink `#0F1B33` glass (66 %, blur 16, 1 px cream border at 18 %), moon cream `#F2E6C8` text, secondary text cream at 72 %, lamplight amber `#F4B03E` (Start, ticks, meter, links) with ink text, success `#8CCB8A`, alert/Stop vermilion `#E5572F`. Light = white glass 62 %, ink `#14223F` text, amber fill with ink text, deep amber `#8A5300` for amber *text*, success `#2F7A44`, alert `#C2411F`. Colours are Flutter theme names, so the light/dark switch re-colours everything (and animates) with no per-widget code.
- **Type:** Oswald (600) only for the title "DuoSound", directly on the sky; Atkinson Hyperlegible for everything else (12 / 14 / 16 / 20). Fonts are in `ui_flet/fonts` (SIL OFL) and bundled in the .exe.
- **Layout:** title, one-line source ("Copying sound from X · Change") and Help sit directly on the scene; two glass surfaces on the main page (headphones list with hairline-separated rows, bottom bar with actions + footer); everything left aligned in a 720 px column so the moon/sun and lake stay visible. Options, source picker, Help and Donate open as glass panels/pages in the same window.
- **Motion:** only the scenery moves, ~12 fps, and it freezes while a movie plays (`ctl.running`), when the window has been unfocused 10 s / minimised / hidden, and when Windows animations are off. Other motion only answers an action (Adjust sync, Options, banner, theme crossfade), 180 ms ease-out.
- **Measured (2026-11-06, fake controller):** animating idle about 22-40 % of one core (Python ~10 %, Flutter client 13-30 %); movie playing (frozen) about 2.7 %; frozen with no updates about 1 %.
