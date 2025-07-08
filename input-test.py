import sounddevice as sd

print("Listing all audio devices:\n")

devices = sd.query_devices()
for i, dev in enumerate(devices):
    print(f"ID {i}: {dev['name']} (Inputs: {dev['max_input_channels']}, Outputs: {dev['max_output_channels']})")
