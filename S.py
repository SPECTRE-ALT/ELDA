# --- ALL IMPORTS ---
import cv2 
import serial
import time
import sys
import numpy as np
import json
import threading
import os
from datetime import datetime
import ollama  # Added from Nexo
import pyttsx3  # Added from Nexo
import speech_recognition as sr  # Added from Nexo

# --- OLLAMA/NEXO CONFIGURATION ---
MODEL_NAME = 'gemma3:1b'  # !! Change this if 'gemma3:1b' is not correct
OLLAMA_HOST_URL = "http://127.0.0.1:11434" # The server you specified

# --- AUTONOMOUS CAR CONFIGURATION ---
CAR_SERIAL_PORT = 'COM14' # !!! CHANGE this to your car's COM port
CAR_BAUD_RATE = 9600
BASE_SPEED = 150
KP_TURN = 0.5
MAX_TARGET_AREA_PERCENT = 40 
TURN_DEAD_ZONE = 30 

# --- ECG/HRV MONITOR CONFIGURATION ---
ECG_SERIAL_PORT = 'COM14' # !!! CHANGE THIS to your ECG's COM port
ECG_BAUD_RATE = 9600

# --- Global States ---
STRESS_DATA_FILE = 'stress_detection_log.json'
CHAT_HISTORY = [] # For storing conversation

STRESS_LEVEL = "Normal"
BLINK_RATE = 0
global_running_flag = True # Used to stop all threads

# --- Car Global States ---
car_currentState = "IDLE" 
car_tracker = None
car_serial_port = None
last_car_command = ""

# --- ECG Global States ---
ecg_serial_port = None
current_heart_rate = 0 
last_ecg_data = "Connecting..."

# --- NEXO/OLLAMA GLOBALS ---
try:
    ollama_client = ollama.Client(host=OLLAMA_HOST_URL)
    ollama_client.list() 
    print(f"✅ Successfully connected to Ollama at: {OLLAMA_HOST_URL}")
except Exception as e:
    print(f"❌ FAILED to connect to Ollama at {OLLAMA_HOST_URL}.")
    print("   Please make sure your Ollama server is running.")
    sys.exit(1)

stt_recognizer = sr.Recognizer()


# --- CAR SERIAL COMMUNICATION ---
def init_car_serial():
    """Tries to connect to the Arduino on the specified port."""
    global car_serial_port
    try:
        car_serial_port = serial.Serial(CAR_SERIAL_PORT, CAR_BAUD_RATE, timeout=1)
        time.sleep(2) 
        print(f"[Car Control]: Successfully connected to Arduino on {CAR_SERIAL_PORT}")
        return True
    except serial.SerialException as e:
        print(f"[Car Control ERROR]: Could not open serial port {CAR_SERIAL_PORT}.")
        print("[Car Control]: The program will run without sending commands.")
        return False

def _send_command_to_serial(command):
    """(Internal) Sends the actual command string to the Arduino."""
    if car_serial_port and car_serial_port.is_open:
        try:
            full_command = command + '\n'
            car_serial_port.write(full_command.encode())
            print(f"[Car Control Sent]: {command}")
        except serial.SerialException as e:
            print(f"[Car Control ERROR]: Error writing to serial port: {e}")
    else:
        print(f"[Car Control Mock]: {command}")

def send_car_command(command):
    """Checks if the command is new before sending."""
    global last_car_command
    if command == last_car_command:
        return
    _send_command_to_serial(command)
    last_car_command = command

def clamp(value, min_val=-255, max_val=255):
    """Clamps a value between a min and max."""
    return max(min_val, min(value, max_val))


# --- ECG/HRV MONITOR FUNCTIONS ---

def init_ecg_serial():
    """Tries to connect to the ECG sensor on its specified port."""
    global ecg_serial_port, last_ecg_data
    
    if CAR_SERIAL_PORT == ECG_SERIAL_PORT and car_serial_port and car_serial_port.is_open:
        print(f"[ECG Monitor ERROR]: Port {ECG_SERIAL_PORT} is already in use by the Car.")
        last_ecg_data = "Port Conflict"
        return False
        
    try:
        ecg_serial_port = serial.Serial(ECG_SERIAL_PORT, ECG_BAUD_RATE, timeout=1)
        time.sleep(2) 
        print(f"[ECG Monitor]: Successfully connected to ECG on {ECG_SERIAL_PORT}")
        last_ecg_data = "Connected"
        return True
    except serial.SerialException as e:
        print(f"[ECG Monitor ERROR]: Could not open serial port {ECG_SERIAL_PORT}.")
        last_ecg_data = "Disconnected"
        return False

def ecg_data_reader_thread():
    """Runs in a separate thread, constantly reading data from the ECG."""
    global last_ecg_data, current_heart_rate, global_running_flag
    
    while global_running_flag:
        if ecg_serial_port and ecg_serial_port.is_open:
            try:
                line = ecg_serial_port.readline()
                if line:
                    decoded_line = line.decode('utf-8').strip()
                    if decoded_line:
                        last_ecg_data = decoded_line
                        # TODO: Add parsing logic here
                        # if decoded_line.startswith("BPM:"):
                        #     current_heart_rate = int(decoded_line.split(":")[1])
            
            except serial.SerialException as e:
                print(f"[ECG Thread ERROR]: {e}")
                last_ecg_data = "Error"
                time.sleep(1) 
            except UnicodeDecodeError:
                pass
        else:
            if not global_running_flag:
                break
            time.sleep(1)
    
    print("[ECG Monitor]: ECG data reader thread stopped.")


# --- STRESS DETECTION (VIDEO PROCESSING) FUNCTIONS ---
def load_stress_data():
    """Load existing stress data from JSON file"""
    try:
        with open(STRESS_DATA_FILE, 'r') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {"stress_events": []}

def save_stress_event(stress_level, blink_rate):
    """Save stress event to JSON file"""
    stress_data = load_stress_data()
    event = {
        "timestamp": datetime.now().isoformat(),
        "stress_level": stress_level,
        "blink_rate": blink_rate,
        "date": datetime.now().strftime("%Y-%m-%d"),
        "time": datetime.now().strftime("%H:%M:%S"),
        "detection_method": "Blink Rate Analysis"
    }
    stress_data["stress_events"].append(event)
    
    with open(STRESS_DATA_FILE, 'w') as f:
        json.dump(stress_data, f, indent=4)
        print(f"\n[System Log]: Stress event logged: {stress_level} at {blink_rate} BPM.")

# --- NEXO VOICE ASSISTANT FUNCTIONS (STT/TTS) ---

def speak(text):
    """
    Prints the text and speaks it using the TTS engine.
    Initializes the engine inside the function to prevent audio conflicts.
    """
    print(f"\n🤖 Nexo:")
    print(text)
    try:
        # Initialize the engine fresh *every time*
        engine = pyttsx3.init()
        engine.say(text)
        engine.runAndWait()
    except Exception as e:
        print(f"Error during speech: {e}")

def listen_for_command():
    """
    Listens for audio from the microphone and converts it to text.
    """
    global stt_recognizer
    with sr.Microphone() as source:
        print("\n[Adjusting for ambient noise...]")
        stt_recognizer.adjust_for_ambient_noise(source, duration=1)
        print("🟢 Listening... Speak your prompt.")
        
        try:
            audio = stt_recognizer.listen(source, timeout=5, phrase_time_limit=10)
        except sr.WaitTimeoutError:
            print("[Timeout. No speech detected.]")
            return None

    try:
        print("[Recognizing speech...]")
        prompt_text = stt_recognizer.recognize_google(audio)
        print(f"👤 You said: {prompt_text}")
        return prompt_text
    
    except sr.UnknownValueError:
        print("Sorry, I could not understand the audio.")
        return None
    except sr.RequestError as e:
        print(f"Could not request results; {e}")
        print("   (NOTE: Speech-to-text requires an internet connection)")
        return None


# --- NEXO BRAIN (THE INTEGRATION HUB) ---

def nexo_brain(prompt):
    """
    This is the new "brain" that combines user input with sensor data.
    """
    global STRESS_LEVEL, BLINK_RATE, last_ecg_data, CHAT_HISTORY, ollama_client
    
    # 1. Create a system prompt with real-time data
    system_prompt = f"""
    You are Nexo, a helpful voice assistant.
    The user is currently in front of a camera.
    
    This is their real-time biometric data:
    - Current Stress Level (from blink rate): {STRESS_LEVEL}
    - Current Blink Rate: {BLINK_RATE} BPM
    - Raw ECG Data: {last_ecg_data}

    RULES:
    1. Be a conversational assistant.
    2. If the user asks "how am I?" or "what's my stress level?", 
       use the biometric data to answer.
    3. If the user asks to control the car (e.g., "follow me" or "stop the car"),
       respond with ONLY the command: "ACTION: [COMMAND]".
       Examples:
       - "ACTION: FOLLOW"
       - "ACTION: STOP"
       - "ACTION: SPIN"
       - "ACTION: RESET"
    4. For all other queries, just answer naturally.
    """
    
    # 2. Add user prompt to history
    CHAT_HISTORY.append({'role': 'user', 'content': prompt})

    # 3. Format messages for Ollama (system prompt + history)
    messages = [
        {'role': 'system', 'content': system_prompt}
    ]
    # Add last 5 messages from history
    messages.extend(CHAT_HISTORY[-5:]) 

    print("\n[Nexo is thinking...]")
    
    try:
        response = ollama_client.chat(
            model=MODEL_NAME,
            messages=messages,
            stream=False
        )
        
        reply_text = response['message']['content']
        
        # 4. Add Nexo's reply to history
        CHAT_HISTORY.append({'role': 'assistant', 'content': reply_text})
        
        return reply_text

    except ollama.ResponseError as e:
        error_message = f"OLLAMA ERROR: {e.error}"
        print(f"\n❌ {error_message}")
        if "model" in e.error and "not found" in e.error:
            return f"Error: The model named {MODEL_NAME} was not found."
        return "Sorry, I had an error with the Ollama model."
    except Exception as e:
        error_message = f"An unexpected error occurred: {e}"
        print(f"\n❌ {error_message}")
        return "Sorry, I ran into an unexpected error."


# --- NEXO VOICE ASSISTANT THREAD LOOP ---

def voice_assistant_loop():
    """
    Main loop to chat with Nexo via voice. Runs in a separate thread.
    """
    global global_running_flag, car_currentState, car_tracker
    
    time.sleep(1) # Wait a moment for other systems to boot
    speak("Hello! Nexo is online. Car and stress monitors are active.")
    
    while global_running_flag:
        try:
            prompt = listen_for_command()

            if not global_running_flag:
                break # Exit if 'q' was pressed in the other thread

            if prompt:
                # 1. Check for local exit command
                if prompt.lower() in ['goodbye nexo', 'exit nexo', 'shutdown', 'stop nexo']:
                    speak("Goodbye!")
                    global_running_flag = False # Signal all threads to stop
                    break
                
                # 2. Send prompt to the "brain" to get a response
                response = nexo_brain(prompt)
                
                # 3. Check if the response is a car command
                if response.startswith("ACTION:"):
                    command = response.replace("ACTION:", "").strip().upper()
                    print(f"[Nexo Action]: Received command '{command}'")
                    
                    if command == "STOP":
                        car_currentState = "IDLE"
                        car_tracker = None
                        send_car_command("S")
                        speak("Stopping the car.")
                    elif command == "SPIN":
                        car_currentState = "SPINNING"
                        car_tracker = None
                        send_car_command("R")
                        speak("Entering spin mode.")
                    elif command == "RESET":
                        car_currentState = "IDLE"
                        car_tracker = None
                        send_car_command("S")
                        speak("Resetting to idle.")
                    elif command == "FOLLOW":
                        speak("Please select the target to follow in the video window.")
                        # This just sets the state; user must still press 'f'
                        car_currentState = "IDLE" 
                        print("[Nexo]: Waiting for user to press 'f' to select target.")
                    else:
                        speak("Sorry, I didn't understand that car command.")
                
                # 4. If not a command, just speak the response
                else:
                    speak(response)
        
        except Exception as e:
            print(f"[Voice Thread ERROR]: {e}")
            time.sleep(1)

    print("[Nexo]: Voice assistant loop stopped.")


# --- MAIN VIDEO & CAR CONTROL LOOP (Runs in Main Thread) ---

EYE_AR_CONSEC_FRAMES = 2 

def main_video_and_car_loop():
    """
    MERGED LOOP: Runs video capture for Stress Detection AND Car Control.
    This MUST run in the main thread for OpenCV's imshow.
    """
    global STRESS_LEVEL, BLINK_RATE, global_running_flag
    global car_currentState, car_tracker, car_serial_port, last_car_command
    global last_ecg_data

    try:
        print("[System]: Loading OpenCV face and eye detectors...")
        face_cascade_path = os.path.join(cv2.data.haarcascades, 'haarcascade_frontalface_default.xml')
        eye_cascade_path = os.path.join(cv2.data.haarcascades, 'haarcascade_eye.xml')

        if not os.path.exists(face_cascade_path):
            raise FileNotFoundError(f"Could not find face cascade: {face_cascade_path}")
        if not os.path.exists(eye_cascade_path):
            raise FileNotFoundError(f"Could not find eye cascade: {eye_cascade_path}")

        face_cascade = cv2.CascadeClassifier(face_cascade_path)
        eye_cascade = cv2.CascadeClassifier(eye_cascade_path)
        
        print("[System]: OpenCV cascades loaded successfully.")

        # --- CAR: Attempt to connect to Arduino ---
        init_car_serial()
        send_car_command("S") 

        cap = cv2.VideoCapture(0)
        if not cap.isOpened():
            raise IOError("Cannot open webcam. Is it in use by another app?")
        
        ret, frame = cap.read()
        if not ret:
            raise IOError("Cannot read frame from webcam.")
            
        frame_height, frame_width = frame.shape[:2]
        frame_center_x = frame_width // 2
        max_safe_area = (frame_width * frame_height) * (MAX_TARGET_AREA_PERCENT / 100.0)

        # Stress Monitor Constants
        MINUTE_INTERVAL = 60 
        current_minute_blinks = 0
        minute_start_time = time.time()
        BLINK_COUNTER = 0 

        print("\n[System]: Starting Main Video Loop (Stress Monitor & Car Control)...")
        print("--- Autonomous Car Controls ---")
        print("   f - Select target to follow")
        print("   s - Stop and enter SPIN mode")
        print("   r - Reset to IDLE")
        print("   q - Quit (stops all systems)")
        print("---------------------------------")
        
        while cap.isOpened() and global_running_flag: # Check the global flag
            ret, frame = cap.read()
            if not ret:
                time.sleep(0.1) 
                continue
            
            frame = cv2.flip(frame, 1)
            
            # --- Handle Key Presses (Car + Quit) ---
            key = cv2.waitKey(30) & 0xFF

            if key == ord('q'):
                print("[System]: 'q' pressed. Shutting down all systems.")
                global_running_flag = False # Signal all threads to stop
                send_car_command("S") 
                break
            
            elif key == ord('s'):
                print("[Car Control]: State change: STOPPED -> SPINNING")
                car_currentState = "SPINNING"
                car_tracker = None 
                send_car_command("R") 
            
            elif key == ord('r'):
                print("[Car Control]: State change: RESET -> IDLE")
                car_currentState = "IDLE"
                car_tracker = None
                send_car_command("S") 
            
            elif key == ord('f') and car_currentState == "IDLE":
                print("[Car Control]: State change: IDLE -> SELECTING")
                cv2.putText(frame, "Draw box and press ENTER", (30, 90), 
                            cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
                cv2.imshow("Nexo (Car Control + Stress Monitor)", frame)
                
                bbox = cv2.selectROI("Nexo (Car Control + Stress Monitor)", frame, fromCenter=False, showCrosshair=True)
                
                if bbox[2] > 0 and bbox[3] > 0:
                    car_tracker = cv2.TrackerCSRT_create()
                    car_tracker.init(frame, bbox)
                    car_currentState = "FOLLOWING"
                    print("[Car Control]: State change: SELECTING -> FOLLOWING")
                else:
                    print("[Car Control]: Selection cancelled.")
                    car_currentState = "IDLE"

            # --- 1. CAR: State Machine Logic ---
            if car_currentState == "FOLLOWING":
                if car_tracker is None:
                    car_currentState = "IDLE"
                    continue

                ok, bbox = car_tracker.update(frame)
                if ok:
                    p1 = (int(bbox[0]), int(bbox[1]))
                    p2 = (int(bbox[0] + bbox[2]), int(bbox[1] + bbox[3]))
                    cv2.rectangle(frame, p1, p2, (0, 255, 0), 2, 1)
                    
                    box_area = bbox[2] * bbox[3]
                    if box_area > max_safe_area:
                        car_currentState = "AVOIDING"
                        print("[Car Control]: State change: FOLLOWING -> AVOIDING")
                        send_car_command("S") 
                    else:
                        target_center_x = int(bbox[0] + bbox[2] / 2)
                        error = target_center_x - frame_center_x
                        
                        command_to_send = ""
                        left_speed = BASE_SPEED
                        right_speed = BASE_SPEED

                        if abs(error) < TURN_DEAD_ZONE:
                            command_to_send = f"M,{int(left_speed)},{int(right_speed)}"
                        else:
                            turn = KP_TURN * error
                            left_speed = clamp(BASE_SPEED + turn)
                            right_speed = clamp(BASE_SPEED - turn)
                            command_to_send = f"M,{int(left_speed)},{int(right_speed)}"
                        
                        send_car_command(command_to_send)
                        cv2.putText(frame, f"Car: FOLLOWING (L:{int(left_speed)}, R:{int(right_speed)})", (10, 90), 
                                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
                else:
                    print("[Car Control]: Tracking failed, returning to IDLE")
                    car_currentState = "IDLE"
                    car_tracker = None
                    send_car_command("S")

            elif car_currentState == "AVOIDING":
                cv2.putText(frame, "Car: AVOIDING (Target too close!)", (10, 90), 
                            cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
                send_car_command("S") 
                
                if car_tracker is not None:
                    ok, bbox = car_tracker.update(frame)
                    if ok:
                        box_area = bbox[2] * bbox[3]
                        if box_area < (max_safe_area * 0.8):
                            print("[Car Control]: State change: AVOIDING -> FOLLOWING")
                            car_currentState = "FOLLOWING"
                    else:
                        car_currentState = "IDLE" 
                        car_tracker = None
                        send_car_command("S")

            elif car_currentState == "SPINNING":
                cv2.putText(frame, "Car: SPINNING", (10, 90), 
                            cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 0, 0), 2)
                send_car_command("R") 

            elif car_currentState == "IDLE":
                cv2.putText(frame, "Car: IDLE (Press 'f' to select)", (10, 90), 
                            cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)

            # --- 2. STRESS: Detection Logic (Updates global vars) ---
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            faces = face_cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5, minSize=(50, 50))
            
            eyes_detected = False
            detected_faces = [] 
            detected_eyes = [] 

            for (x, y, w, h) in faces:
                detected_faces.append((x, y, w, h)) 
                if w > 0:
                    roi_gray = gray[y:y+h, x:x+w]
                    eyes = eye_cascade.detectMultiScale(roi_gray, scaleFactor=1.1, minNeighbors=4, minSize=(20, 20))
                    
                    if len(eyes) > 0:
                        eyes_detected = True
                        for (ex, ey, ew, eh) in eyes:
                            detected_eyes.append((x+ex, y+ey, ew, eh))
                    break 
            
            if eyes_detected:
                BLINK_COUNTER = 0
            else:
                BLINK_COUNTER += 1

            if BLINK_COUNTER == EYE_AR_CONSEC_FRAMES:
                current_minute_blinks += 1

            elapsed_time = time.time() - minute_start_time

            if elapsed_time >= MINUTE_INTERVAL:
                BLINK_RATE = current_minute_blinks # Update global
                
                if BLINK_RATE < 12: 
                    STRESS_LEVEL = "High Stress" # Update global
                elif BLINK_RATE > 25: 
                    STRESS_LEVEL = "Moderate Stress" # Update global
                else:
                    STRESS_LEVEL = "Normal" # Update global
                    
                if STRESS_LEVEL != "Normal":
                    save_stress_event(STRESS_LEVEL, BLINK_RATE)
                    
                print(f"\n[Monitor]: 1-Min BPM: {BLINK_RATE} | Status: {STRESS_LEVEL}")
                current_minute_blinks = 0
                minute_start_time = time.time()

            # --- 3. COMBINED Drawing logic ---
            for (x, y, w, h) in detected_faces:
                cv2.rectangle(frame, (x, y), (x+w, y+h), (255, 0, 0), 2)
            for (x, y, w, h) in detected_eyes:
                cv2.rectangle(frame, (x, y), (x+w, y+h), (0, 255, 0), 2)
                
            color = (0, 255, 0) # Green for Normal
            if STRESS_LEVEL == "Moderate Stress":
                color = (0, 165, 255) # Orange
            elif STRESS_LEVEL == "High Stress":
                color = (0, 0, 255) # Red
                
            cv2.putText(frame, f"Status: {STRESS_LEVEL}", (10, 30), 
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2)
            cv2.putText(frame, f"Blink Rate (BPM): {BLINK_RATE}", (10, 60), 
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)

            # --- Draw ECG Data ---
            cv2.putText(frame, f"ECG Raw: {last_ecg_data}", (10, 120), 
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (200, 200, 0), 2) 

            # --- 4. Show the one, combined frame ---
            cv2.imshow('Nexo (Car Control + Stress Monitor)', frame)

    except Exception as e:
        print(f"[ERROR - OpenCV]: Could not initialize camera or load cascades: {e}")
        print("[System]: Main video loop FAILED to start. Shutting down.")
        global_running_flag = False 
        return
    
    finally:
        # Cleanup
        global_running_flag = False # Ensure all threads stop
        if 'cap' in locals() and cap.isOpened():
            cap.release()
        cv2.destroyAllWindows()
        print("[System]: Main Video Loop Stopped.")
        
        print("[System]: Shutting down car...")
        if car_serial_port and car_serial_port.is_open:
            _send_command_to_serial("S") 
            car_serial_port.close()
            
        print("[System]: Shutting down ECG...")
        if ecg_serial_port and ecg_serial_port.is_open:
            ecg_serial_port.close()


# --- MAIN EXECUTION ---
if __name__ == "__main__":
    
    print("[System]: Initializing All Systems...")

    # 1. Start the ECG Monitor Thread
    print("[System]: Starting ECG Monitor Thread...")
    ecg_thread = None
    if init_ecg_serial(): 
        ecg_thread = threading.Thread(target=ecg_data_reader_thread, daemon=True)
        ecg_thread.start()
        print("[System]: ECG Monitor thread started.")
    else:
        print("[System]: Failed to start ECG Monitor. Continuing without it.")
    
    # 2. Start the Voice Assistant Thread
    print("[System]: Starting Voice Assistant Thread...")
    voice_thread = threading.Thread(target=voice_assistant_loop, daemon=True)
    voice_thread.start()
    
    # 3. Run the STRESS and CAR video loop in the main thread
    main_video_and_car_loop() # This will block until 'q' is pressed or Nexo quits

    # --- Shutdown Sequence ---
    print("[System]: Main thread finished. Waiting for other threads to stop...")
    
    if voice_thread and voice_thread.is_alive():
        voice_thread.join(timeout=2)
        
    if ecg_thread and ecg_thread.is_alive():
        ecg_thread.join(timeout=2)
        
    print("[System]: Shutdown complete.")
