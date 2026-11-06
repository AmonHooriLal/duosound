"""Find audio outputs, classify them and pick a capture source.

How a device's type is decided (most reliable first, works in every Windows language):
1. The Windows registry entry of each output endpoint (HKLM\\...\\MMDevices\\Audio\\Render\\<guid>\\Properties):
   - driver path  {b3f8fa53-...},2  e.g. "{1}.BTHENUM\\{0000110B-...}" (Bluetooth stereo), "{1}.BTHHFENUM\\..." (hands-free),
     "{1}.USB\\VID_..." (USB headset/dongle), "{1}.HDAUDIO\\..." / "{1}.INTELAUDIO\\..." (built-in sound chip);
   - form factor  {1da5d803-...},0  1 speakers, 3 headphones, 5 headset, 8 S/PDIF, 9 HDMI/DisplayPort.
2. Only if the registry can't be read: guess from the name.
Checked against 121 real endpoint names, see PROGRESS.md (2026-11-06 audit)."""
from __future__ import annotations

import re
import warnings
import winreg
from dataclasses import dataclass, field

import soundcard as sc

from . import log_setup

log = log_setup.get("devices")

KIND_BLUETOOTH = "bluetooth"
KIND_HANDSFREE = "hands-free"          # Bluetooth call-quality endpoint (mono, 8-16 kHz) - hidden, see CONTEXT.md
KIND_WIRED = "wired headphones"
KIND_CABLE = "virtual cable"
KIND_HDMI = "hdmi/digital"
KIND_SPEAKERS = "speakers"             # the laptop's built-in speakers (muted while headphones play)
KIND_OTHER = "other"

LISTENER_KINDS = (KIND_BLUETOOTH, KIND_WIRED)   # outputs people wear (ticked by default)
HIDDEN_KINDS = (KIND_HANDSFREE,)                # never shown as source or target

_CABLE_RE = re.compile(r"\bCABLE\b|VB-Audio|Voicemeeter|Virtual Audio", re.I)
_HDMI_RE = re.compile(r"HDMI|Display Audio|Digital Output|DisplayPort|NVIDIA High Definition|Intel\(R\) Display|S/PDIF|SPDIF", re.I)
_HANDSFREE_NAME_RE = re.compile(r"Hands-?Free|\bAG Audio\b", re.I)
# name fallback only (registry unreadable): typical Bluetooth product words
_BT_NAME_RE = re.compile(
    r"Bluetooth|Buds|AirPods|Beats|WH-|WF-|JBL|Bose|Galaxy|Jabra|Soundcore|boAt|Airdopes|Rockerz|OnePlus|Nothing|"
    r"Sennheiser|Momentum|Skullcandy|Marshall|Redmi|Pixel|FreeBuds|Realme|Noise|Edifier|Tozo|QCY|SoundLink|"
    r"Flip|Charge|Boom|Emberton|Sonos|Car Audio|Stereo\b", re.I)
_WIRED_NAME_RE = re.compile(r"Headphone|Headset|Earphone", re.I)
# USB / 2.4 GHz dongle headsets that Windows calls "Speakers (...)" (2026-11-06 audit)
_USB_HEADSET_RE = re.compile(
    r"Corsair|VOID|HS\d{2}|Razer|BlackShark|Kraken|Barracuda|HyperX|Cloud|SteelSeries|Arctis|Logitech|\bG\d{3}\b|PRO X|"
    r"Astro|Turtle Beach|Stealth|INZONE|Quantum|EPOS|Sennheiser|Jabra|Plantronics|Poly|Audeze|Cooler Master|Fifine", re.I)
_SPEAKER_NAME_RE = re.compile(r"Speaker|Realtek|Lautsprecher|Haut-parleur|Altavoces|Altoparlanti", re.I)

_MMDEV = r"SOFTWARE\Microsoft\Windows\CurrentVersion\MMDevices\Audio"
_PKEY_DRIVER_PATH = "{b3f8fa53-0004-438e-9003-51a46e139bfc},2"
_PKEY_FORM_FACTOR = "{1da5d803-d492-4edd-8c23-e0c0ffee7f0e},0"
FF_SPEAKERS, FF_HEADPHONES, FF_HEADSET, FF_SPDIF, FF_HDMI = 1, 3, 5, 8, 9

_BT_STEREO_RE = re.compile(r"\.(BTHENUM|BTHLE|BTHLEDEVICE|BTHLEAUDIO)\\", re.I)
_BT_HANDSFREE_RE = re.compile(r"\.BTHHFENUM\\", re.I)
_USB_RE = re.compile(r"\.USB\\", re.I)

# short plain-words hint per kind (shown next to the source choice and by tools/test_devices.py)
SOURCE_HINT = {
    KIND_CABLE: "best - silent virtual cable",
    KIND_HDMI: "good - silent if no TV/monitor is plugged in",
    KIND_SPEAKERS: "works - DuoSound mutes the speakers while headphones play",
    KIND_WIRED: "not recommended - headphones should listen, not be the source",
    KIND_OTHER: "",
    KIND_BLUETOOTH: "not recommended - a headset can't be the source",
}


@dataclass
class Output:
    id: str
    name: str
    kind: str
    is_default: bool = False
    channels: int = 2
    tags: list[str] = field(default_factory=list)

    @property
    def label(self) -> str:
        extra = " (Windows default)" if self.is_default else ""
        return f"{self.name}{extra}"


@dataclass
class EndpointInfo:
    driver_path: str = ""
    form_factor: int | None = None


def _read_endpoints(flow: str) -> dict[str, EndpointInfo] | None:
    """{guid (lower-case): EndpointInfo} for every endpoint of `flow` ("Render"/"Capture"), from the 64-bit registry
    view (a 32-bit Python sees an empty MMDevices key otherwise). None if nothing could be read."""
    found: dict[str, EndpointInfo] = {}
    try:
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, f"{_MMDEV}\\{flow}", 0, winreg.KEY_READ | winreg.KEY_WOW64_64KEY) as root:
            i = 0
            while True:
                try:
                    guid = winreg.EnumKey(root, i)
                except OSError:
                    break
                i += 1
                info = EndpointInfo()
                try:
                    with winreg.OpenKey(root, f"{guid}\\Properties") as props:
                        for name, attr in ((_PKEY_DRIVER_PATH, "driver_path"), (_PKEY_FORM_FACTOR, "form_factor")):
                            try:
                                setattr(info, attr, winreg.QueryValueEx(props, name)[0])
                            except OSError:
                                pass
                except OSError:
                    continue
                if not isinstance(info.driver_path, str):
                    info.driver_path = ""
                if not isinstance(info.form_factor, int):
                    info.form_factor = None
                found[guid.lower()] = info
    except OSError:
        log.warning("Could not read audio devices from the registry; falling back to name guessing", exc_info=True)
        return None
    if not found:
        log.warning("Registry listed no %s endpoints; falling back to name guessing", flow)
        return None
    return found


def endpoint_registry() -> dict[str, EndpointInfo] | None:
    reg = _read_endpoints("Render")
    if reg:
        log.debug("Registry endpoints: %s", {g: (i.form_factor, i.driver_path[:40]) for g, i in reg.items()})
    return reg


def _guid(dev_id: str) -> str:
    return dev_id.rsplit(".", 1)[-1].lower()


def classify(name: str, info: EndpointInfo | None) -> str:
    """Kind of one output. `info` is its registry entry (None = unknown -> name fallback)."""
    if _CABLE_RE.search(name):
        return KIND_CABLE
    if info is not None and (info.driver_path or info.form_factor is not None):
        path, ff = info.driver_path, info.form_factor
        if _BT_HANDSFREE_RE.search(path):
            return KIND_HANDSFREE
        if _BT_STEREO_RE.search(path):
            return KIND_BLUETOOTH
        if ff in (FF_HDMI, FF_SPDIF):
            return KIND_HDMI
        if ff in (FF_HEADPHONES, FF_HEADSET):
            return KIND_WIRED
        if _USB_RE.search(path):
            # USB / 2.4 GHz dongle headsets often call themselves "Speakers (Corsair ...)": a listener, never muted.
            listener = _WIRED_NAME_RE.search(name) or _USB_HEADSET_RE.search(name) or _BT_NAME_RE.search(name) or ff != FF_SPEAKERS
            return KIND_WIRED if listener else KIND_OTHER
        if ff == FF_SPEAKERS:
            return KIND_SPEAKERS
        if _HDMI_RE.search(name):
            return KIND_HDMI
        return KIND_OTHER
    # ---- name fallback (registry unreadable) ----
    if _HANDSFREE_NAME_RE.search(name):
        return KIND_HANDSFREE
    if _HDMI_RE.search(name):
        return KIND_HDMI
    if _BT_NAME_RE.search(name):
        return KIND_BLUETOOTH
    if _WIRED_NAME_RE.search(name):
        return KIND_WIRED
    if _SPEAKER_NAME_RE.search(name):
        return KIND_SPEAKERS
    return KIND_OTHER


def list_outputs(include_hidden: bool = False) -> list[Output]:
    """All usable output devices, classified. Hands-free endpoints are left out unless include_hidden."""
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        speakers = sc.all_speakers()
        try:
            default_id = sc.default_speaker().id
        except Exception:  # noqa: BLE001
            default_id = ""
    reg = endpoint_registry()
    outs = []
    for s in speakers:
        info = (reg.get(_guid(s.id)) or EndpointInfo()) if reg is not None else None
        outs.append(Output(id=s.id, name=s.name, kind=classify(s.name, info), is_default=(s.id == default_id),
                           channels=getattr(s, "channels", 2)))
    log.info("Found %d outputs: %s", len(outs), "; ".join(f"{o.name} [{o.kind}{', default' if o.is_default else ''}]" for o in outs))
    if not include_hidden:
        hidden = [o.name for o in outs if o.kind in HIDDEN_KINDS]
        if hidden:
            log.info("Hidden (hands-free call mode would lower the quality): %s", hidden)
        outs = [o for o in outs if o.kind not in HIDDEN_KINDS]
    return outs


def laptop_microphones() -> list:
    """Real (non-loopback) microphones that are NOT on a Bluetooth headset - used for calibration.
    Opening a headset mic would switch it into low-quality hands-free mode, so those are excluded."""
    cap = _read_endpoints("Capture") or {}
    bt = {g for g, i in cap.items() if re.search(r"\.BTH", i.driver_path, re.I)}
    mics = []
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        for m in sc.all_microphones(include_loopback=False):
            if _guid(m.id) in bt or re.search(r"Headset|Hands-Free|Bluetooth|Buds|AirPods", m.name, re.I):
                continue
            mics.append(m)
    log.info("Laptop microphones for calibration: %s", [m.name for m in mics] or "none")
    return mics


SOURCE_RANK = {KIND_CABLE: 0, KIND_HDMI: 1, KIND_SPEAKERS: 2, KIND_OTHER: 3, KIND_WIRED: 8, KIND_BLUETOOTH: 9}


def source_candidates(outs: list[Output]) -> list[Output]:
    """Outputs that can be the capture source, best first. Headphones come last (they should be targets)."""
    return sorted([o for o in outs if o.kind not in HIDDEN_KINDS], key=lambda o: (SOURCE_RANK.get(o.kind, 5), not o.is_default))


def suggest_source(outs: list[Output]) -> Output | None:
    cands = [o for o in source_candidates(outs) if o.kind not in LISTENER_KINDS]
    return cands[0] if cands else None


def suggest_targets(outs: list[Output], source_id: str | None) -> list[Output]:
    return [o for o in outs if o.kind in LISTENER_KINDS and o.id != source_id]


def laptop_speakers(outs: list[Output]) -> list[Output]:
    """The laptop's built-in speakers (what DuoSound mutes while headphones play)."""
    return [o for o in outs if o.kind == KIND_SPEAKERS]
