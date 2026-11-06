"""DuoSound - play one laptop's audio on several Bluetooth headphones, in sync."""
__version__ = "0.1.2"

SAMPLERATE = 48000   # Hz - native rate of the Windows audio engine and A2DP
CHANNELS = 2         # stereo
BLOCK = 480          # frames per block = 10 ms (default; Engine uses its own self.block)

MUTEX_NAME = "Local\\DuoSound.SingleInstance"   # shared by main.py and main_lite.py
BLOCK_SIZES = {10: 480, 20: 960}                 # valid block_size_ms -> frames per block
