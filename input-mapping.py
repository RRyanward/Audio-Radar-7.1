import sounddevice as sd
import numpy as np
from scipy.signal import butter, lfilter
import time

# Bandpass filter setup: 400-2500Hz (good for footsteps etc.)
def butter_bandpass(lowcut, highcut, fs, order=4):
    nyq = 0.5 * fs
    b, a = butter(order, [lowcut / nyq, highcut / nyq], btype='band')
    return b, a

def bandpass_filter(data, b, a):
    return lfilter(b, a, data)

fs = 44100
channels = 8
gain = 1.0

b, a = butter_bandpass(400, 2500, fs)

def audio_callback(indata, frames, time_info, status):
    filtered = [bandpass_filter(indata[:, i], b, a) for i in range(channels)]
    levels = [np.sqrt(np.mean(ch**2)) * gain for ch in filtered]

    print(f"RMS Levels @ {time.strftime('%H:%M:%S')}:")
    for i, lvl in enumerate(levels):
        print(f"  Channel {i}: {lvl:.6f}")
    print("-" * 40)

def main():
    print("Starting audio capture. Play sound on ONE speaker at a time in Voicemeeter.")
    device_name = input("Enter the exact input device name or index (leave blank for default): ")

    try:
        device = int(device_name)
    except:
        device = device_name if device_name else None

    with sd.InputStream(device=device, channels=channels, samplerate=fs, callback=audio_callback, blocksize=1024):
        print("Streaming... Press Ctrl+C to stop.")
        while True:
            time.sleep(1)

if __name__ == "__main__":
    main()
