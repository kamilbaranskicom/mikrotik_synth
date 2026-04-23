# edit to your needs and rename to config.py

# --- Router Configuration ---
ROUTER_IP = '192.168.88.1'
ROUTER_USER = 'admin+ct'
ROUTER_PASS = 'password'

# Name of your virtual MIDI port (e.g., from loopMIDI)
MIDI_PORT_NAME = 'loopMIDI Port MikroTik' 

# 'Infinite' note duration
LONG_BEEP = "10s"
# Micro beep to interrupt the current sound
STOP_BEEP = "1ms"

# --- Pitch Bend Settings ---
PITCH_BEND_RANGE = 2.0  # Maximum bend in semitones (usually +/- 2)
MIN_FREQ_CHANGE = 1.0   # Minimum Hz difference to trigger a new SSH command
PITCH_THROTTLE = 0.04   # Minimum time (seconds) between pitch bend updates
