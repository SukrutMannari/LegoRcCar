#!/usr/bin/env python3
from ev3dev2.motor import LargeMotor, MediumMotor, MoveTank, OUTPUT_A, OUTPUT_B, OUTPUT_C 
from ev3dev2.sound import Sound 
from evdev import InputDevice, ecodes
import sys

# --- CONFIGURATION (Confirmed for NeoGlow Controller) ---
CONTROLLER_PATH = '/dev/input/event2' 
ACCEL_CODE = 313    # ZR Button (FORWARD)
REVERSE_CODE = 314  # Select Button (REVERSE)
BRAKE_CODE = 312    # ZL Button (DEDICATED BRAKE)
HORN_CODE = 304     # BTN_SOUTH (A Button)
HORN2_CODE = 305    # BTN_EAST (B Button)
STOP_SOUND_CODE = 308 # BTN_WEST (X Button)
STEERING_AXIS_CODE = 0 # Left Stick X-Axis

# --- TRIM CONFIGURATION ---
TRIM_AXIS_CODE = 16 # ABS_HAT0X (D-Pad Left/Right)
TRIM_STEP = 1       # 1 degree for exact control
MAX_TRIM = 45       # Maximum allowable trim adjustment

FULL_SPEED = 100    
AXIS_MIN = 0
AXIS_MAX = 255
AXIS_MID = 128      
STEERING_DEADZONE = 10 
STEERING_MAX_ANGLE = 90  
STEERING_SPEED = 720     
STEERING_HOME_POSITION = 0

# --- GLOBAL STATE & SETUP ---
steering_trim = 0 
tank = MoveTank(OUTPUT_B, OUTPUT_C) # Drive Motors on B and C
steering_motor = MediumMotor(OUTPUT_A)
speaker = Sound()
steering_motor.stop_action = 'coast' 
steering_motor.reset()


# --- Helper Function ---
def normalize_steering(raw_value):
    """
    Normalizes the controller's X-axis value (0 to 255) to a target angle (-90 to 90),
    applying the current trim offset.
    """
    
    is_centered_on_stick = AXIS_MID - STEERING_DEADZONE <= raw_value <= AXIS_MID + STEERING_DEADZONE
    
    if is_centered_on_stick:
        # If stick is centered, return the current trim value
        return steering_trim
    else:
        # Joystick Proportional Calculation (Absolute angle relative to zero)
        normalized_val = raw_value - AXIS_MID
        target_angle = (normalized_val / (AXIS_MAX - AXIS_MID)) * STEERING_MAX_ANGLE
        # Apply the Trim offset
        return int(target_angle + steering_trim)

# --- Main Logic ---

print("Attempting to open controller at {}...".format(CONTROLLER_PATH))
try:
    dev = InputDevice(CONTROLLER_PATH)
    print("Successfully connected to: {}".format(dev.name))
except FileNotFoundError:
    print("Error: Controller not found at {}. Check your USB connection and path.".format(CONTROLLER_PATH))
    sys.exit(1)
except PermissionError:
    print("Error: Permission denied. You must run the script with 'sudo'.")
    sys.exit(1)


print("Controller ready. ZR/Select for Drive. ZL for Brake. D-Pad Left/Right for Trim. A for Horn, B for Horn 2, X to Stop Sound.")

try:
    global steering_trim
    
    for event in dev.read_loop():
        
        # --- Handle Axis Events (Steering Stick) ---
        if event.type == ecodes.EV_ABS and event.code == STEERING_AXIS_CODE:
            
            target_angle = normalize_steering(event.value)
            is_centered_on_stick = AXIS_MID - STEERING_DEADZONE <= event.value <= AXIS_MID + STEERING_DEADZONE
            
            if is_centered_on_stick:
                current_position = steering_motor.position
                # Stutter fix: only command motor if current position is off by more than 1 degree
                if abs(current_position - target_angle) > 1:
                    steering_motor.run_to_abs_pos(position_sp=target_angle, speed_sp=STEERING_SPEED, stop_action='coast')
            else:
                # If stick is active, always command movement
                steering_motor.run_to_abs_pos(position_sp=target_angle, speed_sp=STEERING_SPEED, stop_action='coast')
            
        # --- Handle D-Pad Trim Events ---
        elif event.type == ecodes.EV_ABS and event.code == TRIM_AXIS_CODE and event.value != 0:
            
            # event.value will be -1 (Left) or 1 (Right)
            if event.value == -1: # D-Pad Left
                steering_trim -= TRIM_STEP
            elif event.value == 1: # D-Pad Right
                steering_trim += TRIM_STEP

            steering_trim = max(-MAX_TRIM, min(MAX_TRIM, steering_trim))
            
            print("Steering Trim updated: {} degrees".format(steering_trim))
            speaker.speak("Trim {} degrees".format(steering_trim))
            
            # Immediately move steering motor to the new trimmed center position
            steering_motor.run_to_abs_pos(position_sp=steering_trim, speed_sp=STEERING_SPEED, stop_action='coast')

        # --- Handle Key Events (Drive and Sound) ---
        elif event.type == ecodes.EV_KEY:
            
            # ZR (FORWARD)
            if event.code == ACCEL_CODE:
                if event.value == 1: 
                    tank.on(FULL_SPEED, FULL_SPEED) 
                elif event.value == 0:
                    tank.off(brake=False)

            # Select (REVERSE)
            elif event.code == REVERSE_CODE:
                if event.value == 1: 
                    tank.on(-FULL_SPEED, -FULL_SPEED) 
                elif event.value == 0:
                    tank.off(brake=False) 
            
            # ZL (BRAKE)
            elif event.code == BRAKE_CODE:
                if event.value == 1:
                    tank.off(brake=True) 
                elif event.value == 0:
                    tank.off(brake=False) 
            
            # HORN (A Button)
            elif event.code == HORN_CODE:
                if event.value == 1: 
                    # File path is /home/robot/VSCODE/Horn.wav
                    speaker.play_file("/home/robot/VSCODE/Horn.wav", play_type=1)
            
            # HORN 2 (B Button)
            elif event.code == HORN2_CODE:
                if event.value == 1:
                    # File path is /home/robot/VSCODE/Horn2.wav
                    speaker.play_file("/home/robot/VSCODE/Horn2.wav", play_type=1)

            # STOP SOUND (X Button)
            elif event.code == STOP_SOUND_CODE:
                if event.value == 1: 
                    speaker.stop()
                
except KeyboardInterrupt:
    print("\nProgram interrupted. Stopping motors.")
    tank.off(brake=False) 
    steering_motor.stop_action = 'brake' 
    steering_motor.off() 
finally:
    tank.off(brake=False) 
    steering_motor.stop_action = 'brake' 
    steering_motor.off()
