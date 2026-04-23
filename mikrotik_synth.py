import time
import mido
import paramiko
import sys
import socket
import threading


# Import settings from the external config.py file
from config import (
    ROUTER_IP, ROUTER_USER, ROUTER_PASS, MIDI_PORT_NAME,
    LONG_BEEP, STOP_BEEP, PITCH_BEND_RANGE, MIN_FREQ_CHANGE, PITCH_THROTTLE
)

def calculate_frequency(midi_note, pitch_value=0):
    """Calculates frequency including pitch bend."""
    # Convert pitch value (-8192 to 8191) to semitones
    bend_semitones = (pitch_value / 8192.0) * PITCH_BEND_RANGE
    actual_note = midi_note + bend_semitones
    
    # Calculate final frequency
    freq = round(440.0 * (2.0 ** ((actual_note - 69) / 12.0)), 2)
    return freq

def find_actual_port_name(target_name):
    """Finds the actual system port name that contains the target string."""
    available_ports = mido.get_input_names()
    for port in available_ports:
        if target_name in port:
            return port
    return None

def consume_output(shell):
    """Continuously clears the SSH incoming buffer."""
    while True:
        try:
            if shell.recv_ready():
                shell.recv(4096)
            else:
                time.sleep(0.005)
        except Exception:
            break

def main():
    actual_port_name = find_actual_port_name(MIDI_PORT_NAME)
    
    if not actual_port_name:
        print(f"Error: Could not find MIDI port containing '{MIDI_PORT_NAME}'")
        sys.exit(1)

    print("Connecting to RouterOS via SSH...")
    ssh_client = paramiko.SSHClient()
    ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    
    try:
        ssh_client.connect(
            ROUTER_IP, 
            username=ROUTER_USER, 
            password=ROUTER_PASS,
            look_for_keys=False,
            allow_agent=False
        )
        
        transport = ssh_client.get_transport()
        transport.sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)

        shell = ssh_client.invoke_shell()
        print("SSH connection established. Zero-latency & Pitchbend mode enabled.")
        
        threading.Thread(target=consume_output, args=(shell,), daemon=True).start()
        time.sleep(0.5)

        print(f"Listening to MIDI port: {actual_port_name}")
        
        # Note stack for monophonic "last note priority" behavior
        active_notes = []
        current_pitch_val = 0
        last_sent_freq = 0.0
        last_bend_time = 0.0  # Time tracker for throttling

        with mido.open_input(actual_port_name) as inport:
            for msg in inport:
                
                # --- NOTE ON ---
                if msg.type == 'note_on' and msg.velocity > 0:
                    if msg.note in active_notes:
                        active_notes.remove(msg.note)
                    active_notes.append(msg.note) # Add to top of stack
                    
                    active_note = active_notes[-1]
                    freq = calculate_frequency(active_note, current_pitch_val)
                    
                    cmd = f":beep frequency={freq} length={LONG_BEEP}\r"
                    shell.send(cmd)
                    last_sent_freq = freq
                    print(f"ON   | Note: {active_note} | Freq: {freq}Hz")
                
                # --- NOTE OFF ---    
                elif msg.type == 'note_off' or (msg.type == 'note_on' and msg.velocity == 0):
                    if msg.note in active_notes:
                        active_notes.remove(msg.note)
                        
                    if len(active_notes) > 0:
                        # Re-trigger the previous note in the stack
                        active_note = active_notes[-1]
                        freq = calculate_frequency(active_note, current_pitch_val)
                        cmd = f":beep frequency={freq} length={LONG_BEEP}\r"
                        shell.send(cmd)
                        last_sent_freq = freq
                        print(f"BACK | Note: {active_note} | Freq: {freq}Hz")
                    else:
                        # Stack is empty, kill sound
                        cmd = f":beep frequency=20 length={STOP_BEEP}\r"
                        shell.send(cmd)
                        print(f"OFF  | Note: {msg.note}")
                
                # --- PITCH BEND ---
                elif msg.type == 'pitchwheel':
                    current_pitch_val = msg.pitch
                    current_time = time.time()
                    
                    # Throttle updates based on time, but ALWAYS allow returning to center (pitch 0)
                    if (current_time - last_bend_time >= PITCH_THROTTLE) or msg.pitch == 0:
                        if len(active_notes) > 0:
                            active_note = active_notes[-1]
                            freq = calculate_frequency(active_note, current_pitch_val)
                            
                            # Also throttle based on frequency change, unless returning to center
                            if abs(freq - last_sent_freq) >= MIN_FREQ_CHANGE or msg.pitch == 0:
                                cmd = f":beep frequency={freq} length={LONG_BEEP}\r"
                                shell.send(cmd)
                                last_sent_freq = freq
                                last_bend_time = current_time
                                print(f"BEND | Note: {active_note} | Freq: {freq}Hz | Pitch: {msg.pitch}")

    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)
    finally:
        ssh_client.close()
        print("SSH connection closed.")

if __name__ == "__main__":
    main()