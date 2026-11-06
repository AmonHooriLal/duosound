# Product

<!-- impeccable:product-schema 1 -->

## Platform

Windows desktop app (Python + tkinter window with a tray icon), shipped as a single `.exe`.
Not web, iOS or Android.

## Users
The public: anyone with a Windows laptop who wants two or more people to watch one movie or video together, each on
their own Bluetooth (or wired) headphones, without disturbing others in the room. Mostly non-technical people. They
pair headphones in Windows, open DuoSound, press Start and play the movie.

## Product Purpose
DuoSound copies whatever the laptop plays to several headphones at once and keeps them in sync, so everyone hears
the same moment with no echo between headsets, for a whole film. Success is that people press Start and it just works.

## Positioning
Windows can play to only one ordinary (A2DP) Bluetooth headset at a time. Windows 11 "Shared audio" exists, but only
for LE Audio hardware. DuoSound works with the ordinary headphones people already own: it gives each headset its own delay
and corrects clock drift automatically, so they stay aligned over a two-hour movie.

## Operating Context
- Home use: a movie night or a flight/train, with 2–5 people and a mix of earbud and headphone brands.
- The movie plays in any app (browser, VLC, Netflix). DuoSound runs beside it, often minimised to the tray.
- Sync is set by Calibrate (the laptop mic hears chirps from each headset) or by ear (Delay slider).

## Capabilities and Constraints
- Captures a "source" output by WASAPI loopback (VB-CABLE, an unused HDMI output, or the laptop speakers) and plays
  it on each ticked headset.
- Mutes the laptop speakers while headphones play; Windows' sound settings are always put back on Stop or the next launch.
- Headset microphones are never opened, because that would switch the headset to low-quality hands-free mode.
- One Bluetooth radio carries every stream, so 2 headsets are reliable and 3–5 depend on the adapter (a USB dongle helps).
- Total Bluetooth latency of about 150–350 ms means lip sync can be slightly late. Players such as VLC can compensate.
- Open decisions: licence, distribution channel (e.g. GitHub Releases), and code signing (affects the Windows
  SmartScreen "unknown publisher" warning).

## Brand Commitments
- Name: **DuoSound**.
- Creator: **Amon Lal**, credited in the app ("Made by Amon Lal"), the About page and the README.
- Donations: a Donate page showing Amon's UPI QR code (`Donate ME QR/GooglePay_QR.png`, UPI ID `amonh7-1@okicici`).
  It is never a popup and never nags.

## Evidence on Hand
- Real tests on Amon's laptop (2026-11-05/06): OnePlus Buds 4 + OnePlus Bullets Wireless Z3 played together with 0 underruns
  and 0 jumps, and a headset switched off mid-play reconnected by itself in 6 s (see PROGRESS.md).
- A device-name audit covered 121 endpoint names across major brands (see PROGRESS.md).
- No user testimonials, download numbers or press exist. Do not invent any.

## Product Principles
1. **Zero setup first.** The defaults must be right: auto-pick the source, auto-tick the headphones, auto-mute the speakers.
2. **Never leave the user's PC changed.** Every Windows sound setting DuoSound touches is put back.
3. **Plain words.** Every label and message makes sense to someone who doesn't know what "loopback" or "A2DP" means,
   and every problem comes with a "how to fix".
4. **Sync is sacred.** No echo between headsets. Anything that risks sync (hands-free endpoints, a headset as source) is hidden
   or warned about.
