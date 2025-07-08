Audio Radar Overlay — How to Use
Requirements
Python 3.8 or higher

Dependencies: numpy, scipy, sounddevice, PyQt6
Install via pip:

bash
Copy
Edit
pip install numpy scipy sounddevice PyQt6
Running from Source
Clone or download this repository.

Make sure your audio input device supports 7.1 channel input (e.g., Voicemeeter 7.1 output).

Run the app with:

bash
Copy
Edit
python "audio radar.py"
On first launch, select your audio input device, adjust gain and thresholds, then click Apply.

The overlay will appear fullscreen, showing directional audio lightbars indicating sound source locations.

Building an Executable
To create a standalone Windows executable:

Install PyInstaller (if you don’t have it):

bash
Copy
Edit
pip install pyinstaller
Run this command in your project folder:

bash
Copy
Edit
pyinstaller --onefile --windowed --icon=tray_icon.ico "audio radar.py"
After completion, the executable will be in the dist folder as audio radar.exe.

Run audio radar.exe to launch the overlay without needing Python installed.

Usage Tips
Ensure your audio routing software (e.g., Voicemeeter) is set up to output discrete 7.1 channels to the selected input device.

Adjust Gain, Yellow Threshold, and Red Threshold sliders to fine-tune the overlay sensitivity and color transitions based on your in-game audio.

The lightbars will color fade from yellow (medium loudness) to red (very loud) for immersive directional audio feedback.

Troubleshooting
If no lightbars appear, check your input device selection and audio routing configuration.

Use the tray icon menu to toggle overlay visibility or change input device at any time.

Let me know if you want me to format it in markdown or include badges, images, or GIFs for your GitHub!
