import ollama
import pyttsx3
import speech_recognition as sr
import sys
import pyautogui  
import time       
import json
import os        
import cv2                 
import pytesseract         
import numpy as np
import tkinter as tk        # <-- ADDED: For the breathing app
from threading import Thread  # <-- ADDED: To run the app without blocking
import webbrowser           # <-- ADDED: To open Spotify reliably

# --- CONFIGURATION ---
MODEL_NAME = 'gemma3:1b'  # !! Change this if 'gemma3:1b' is not correct
OLLAMA_HOST_URL = "http://127.0.0.1:11434" # The server you specified
CHAT_HISTORY_FILE = 'chathistory.json' 
SCROLL_AMOUNT = 500 # Number of pixels to scroll per command
RELAX_URL = "https://open.spotify.com/playlist/37i9dQZF1DWU0ScTcjAxGP" # A "Relax & Unwind" playlist

# --- NEW: List of "trigger words" for command mode ---
COMMAND_TRIGGER_WORDS = [
    "open", "launch", "start",  # For apps & URL
    "click", "press",            # For clicking and key presses
    "type", "write",             # For typing
    "scroll",                    # For scrolling
    "copy", "paste", "save", "undo", "close", "switch", # For hotkeys
    "find", "move"               # For click_text and move_center
]
# --- END CONFIGURATION ---

# --- TESSERACT-OCR CONFIGURATION ---
# If you installed Tesseract somewhere non-standard, uncomment and set the path.
# On Windows, the default is often:
# pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'
# On Linux, it's usually in the PATH and doesn't need this.
# --- END TESSERACT-OCR CONFIGURATION ---


# 1. Initialize Speech-to-Text (STT)
r = sr.Recognizer()

# 2. Initialize Ollama
try:
    client = ollama.Client(host=OLLAMA_HOST_URL)
    client.list() 
    print(f"✅ Successfully connected to Ollama at: {OLLAMA_HOST_URL}")
except Exception as e:
    print(f"❌ FAILED to connect to Ollama at {OLLAMA_HOST_URL}.")
    print("   Please make sure your Ollama server is running.")
    sys.exit(1)

# 3. Text-to-Speech (TTS) Function
def speak(text):
    """
    Prints the text and speaks it using the TTS engine.
    Initializes the engine inside the function to prevent conflicts.
    """
    if not text: # Don't speak if text is empty
        return
        
    print(f"\n🤖 Nexo:")
    print(text)
    try:
        # Initialize the engine fresh *every time*
        engine = pyttsx3.init()
        engine.say(text)
        engine.runAndWait()
    except Exception as e:
        print(f"Error during speech: {e}")

# 4. Speech-to-Text (STT) Function
def listen_for_command():
    """
    Listens for audio from the microphone and converts it to text.
    """
    with sr.Microphone() as source:
        print("\n[Adjusting for ambient noise...]")
        r.adjust_for_ambient_noise(source, duration=1)
        print("🟢 Listening... Speak your prompt.")
        
        try:
            audio = r.listen(source, timeout=5, phrase_time_limit=10)
        except sr.WaitTimeoutError:
            print("[Timeout. No speech detected.]")
            return None

    try:
        print("[Recognizing speech...]")
        prompt_text = r.recognize_google(audio)
        print(f"👤 You said: {prompt_text}")
        return prompt_text
    
    except sr.UnknownValueError:
        print("Sorry, I could not understand the audio.")
        return None
    except sr.RequestError as e:
        print(f"Could not request results; {e}")
        print("   (NOTE: Speech-to-text requires an internet connection)")
        return None

# 5. Automation Functions (REWRITTEN WITH PYAUTOGUI)

# --- NEW: Breathing Exercise App ---
class BreathingExercise(tk.Toplevel):
    def __init__(self):
        super().__init__()
        self.title("Breathing Exercise")
        self.geometry("400x400")
        self.configure(bg="#2b2b2b")
        
        # Make it stay on top
        self.attributes("-topmost", True)
        
        self.canvas = tk.Canvas(self, width=380, height=300, bg="#2b2b2b", highlightthickness=0)
        self.canvas.pack(pady=20)
        
        self.ball = self.canvas.create_oval(140, 100, 240, 200, fill="#00d0ff", outline="")
        
        self.label = tk.Label(self, text="Breathe In...", fg="white", bg="#2b2b2b", font=("Arial", 20))
        self.label.pack()
        
        self.min_size = (140, 100, 240, 200)
        self.max_size = (90, 50, 290, 250)
        self.breathing_out = False
        
        # Bind the close event
        self.protocol("WM_DELETE_WINDOW", self.on_close)
        
        self.running = True
        self.animate()

    def on_close(self):
        self.running = False
        self.destroy()

    def animate(self):
        if not self.running:
            return

        if self.breathing_out:
            self.label.config(text="Breathe Out...")
            self.animate_ball(self.max_size, self.min_size, 4000) # 4 sec out
        else:
            self.label.config(text="Breathe In...")
            self.animate_ball(self.min_size, self.max_size, 4000) # 4 sec in
            
        self.breathing_out = not self.breathing_out
        
        if self.running:
            self.after(4500, self.animate) # Start next cycle

    def animate_ball(self, start_coords, end_coords, duration):
        steps = 100
        delay = duration // steps
        
        for i in range(steps + 1):
            if not self.running: # Stop animation if window is closed
                break
                
            fraction = i / steps
            
            # Linear interpolation for each coordinate
            x1 = start_coords[0] + (end_coords[0] - start_coords[0]) * fraction
            y1 = start_coords[1] + (end_coords[1] - start_coords[1]) * fraction
            x2 = start_coords[2] + (end_coords[2] - start_coords[2]) * fraction
            y2 = start_coords[3] + (end_coords[3] - start_coords[3]) * fraction
            
            try:
                self.canvas.coords(self.ball, x1, y1, x2, y2)
                self.canvas.update()
                self.after(delay)
            except tk.TclError:
                # Window was closed during animation
                break

def run_breathing_app():
    # This function is run in a separate thread
    try:
        root = tk.Tk()
        root.withdraw()  # Hide the main root window
        app = BreathingExercise()
        app.mainloop()
    except Exception as e:
        print(f"Error starting breathing app: {e}")

def safe_open_breathing_exercise():
    try:
        # Start the Tkinter app in a new thread
        # This prevents it from blocking the main_chat_loop
        Thread(target=run_breathing_app, daemon=True).start()
        return True
    except Exception as e:
        print(f"Failed to start breathing app thread: {e}")
        return False
# --- END Breathing Exercise ---


def safe_open_app(app_name):
    """
    Opens an application by pressing the Win key, typing the name,
    and pressing Enter.
    """
    try:
        pyautogui.press('win')
        time.sleep(0.5) # Wait for start menu
        
        # Use pyautogui.write for typing
        pyautogui.write(app_name, interval=0.05)
             
        time.sleep(0.5) # Wait for search
        pyautogui.press('enter')
        return True
    except Exception as e:
        print(f"PyAutoGUI Error (Open App): {e}")
        return False

# --- NEW: Open URL Function ---
def safe_open_url(url):
    """
    Opens a URL in the default web browser.
    """
    try:
        webbrowser.open(url)
        return True
    except Exception as e:
        print(f"Webbrowser Error (Open URL): {e}")
        return False


def safe_type_string(text_to_type, press_enter=False):
    """
    Types a string using pyautogui.
    Optionally presses Enter after typing.
    """
    try:
        # interval adds a small delay between keys for reliability
        pyautogui.write(text_to_type, interval=0.05)
        
        if press_enter:
            time.sleep(0.1) # Small pause before pressing enter
            pyautogui.press('enter')
            
        return True
    except Exception as e:
        print(f"PyAutoGUI Error (Type): {e}")
        return False

def safe_move_center():
    """
    Moves the mouse to the center of the screen.
    """
    try:
        # Get screen size
        width, height = pyautogui.size()
        # Move to center, taking 0.25 seconds
        pyautogui.moveTo(width / 2, height / 2, duration=0.25)
        return True
    except Exception as e:
        print(f"PyAutoGUI Error (Move): {e}")
        return False

def safe_click():
    """
    Clicks the mouse at its current position.
    """
    try:
        pyautogui.click()
        return True
    except Exception as e:
        print(f"PyAutoGUI Error (Click): {e}")
        return False

def safe_click_text(text_to_click):
    """
    Finds text on the screen using Tesseract-OCR and clicks on it.
    """
    try:
        # 1. Take a screenshot
        screenshot = pyautogui.screenshot()
        # Convert to an OpenCV image
        img = cv2.cvtColor(np.array(screenshot), cv2.COLOR_RGB2BGR)
        # Convert to grayscale for better OCR
        gray = cv2.cvtColor(img, cv2.COLOR_BGR_GRAY)

        # 2. Use Tesseract to find all text data
        print(f"[OCR] Searching for text: '{text_to_click}'...")
        data = pytesseract.image_to_data(gray, output_type=pytesseract.Output.DICT)
        
        n_boxes = len(data['level'])
        for i in range(n_boxes):
            # 3. Check if the found text matches
            found_text = data['text'][i].strip().lower()
            target_text = text_to_click.lower() # User's request

            # Skip empty strings found by OCR
            if not found_text:
                continue

            # --- MODIFIED LOGIC ---
            # Check for a match in *both* directions
            # 1. User request "file" is in OCR text "file menu"
            # 2. OCR text "down" is in user request "downloads" (handles broken words)
            if (target_text in found_text or found_text in target_text):
                
                # 4. Get coordinates
                (x, y, w, h) = (data['left'][i], data['top'][i], data['width'][i], data['height'][i])
                
                # Calculate center
                center_x = x + (w // 2)
                center_y = y + (h // 2)

                print(f"[OCR] Found! Moving to ({center_x}, {center_y}) and clicking.")
                
                # 5. Move and Click
                pyautogui.moveTo(center_x, center_y, duration=0.25)
                pyautogui.click()
                return True

        print(f"[OCR] Error: Could not find text '{text_to_click}' on the screen.")
        return False
        
    except Exception as e:
        if "tesseract is not installed" in str(e).lower():
            print("\n" + "="*50)
            print("FATAL ERROR: TESSERACT-OCR NOT FOUND")
            print("Please install the Tesseract-OCR engine (not just the pip package).")
            print("See instructions: https://github.com/UB-Mannheim/tesseract/wiki")
            print("="*50 + "\n")
        else:
            print(f"PyAutoGUI/OCR Error (Click Text): {e}")
        return False

def safe_key_press(key):
    """
    Presses a single key (e.g., 'enter', 'esc', 'f5').
    """
    try:
        pyautogui.press(key)
        return True
    except Exception as e:
        print(f"PyAutoGUI Error (Key Press): {e}")
        return False

def safe_key_combination(keys):
    """
    Presses a key combination (e.g., ['ctrl', 'c']).
    """
    try:
        pyautogui.hotkey(*keys) # Unpacks the list into arguments
        return True
    except Exception as e:
        print(f"PyAutoGUI Error (Key Combination): {e}")
        return False

def safe_scroll(direction):
    """
    Scrolls up or down.
    """
    try:
        amount = 0
        if direction == "up":
            amount = SCROLL_AMOUNT
        elif direction == "down":
            amount = -SCROLL_AMOUNT
        else:
            return False # Invalid direction
            
        pyautogui.scroll(amount)
        return True
    except Exception as e:
        print(f"PyAutoGUI Error (Scroll): {e}")
        return False
# --- END Automation Functions ---


# --- Chat History Functions ---
def load_chat_history():
    """Loads chat history from the JSON file, or returns a default."""
    if os.path.exists(CHAT_HISTORY_FILE):
        try:
            with open(CHAT_HISTORY_FILE, 'r') as f:
                history = json.load(f)
                # Ensure history is a list
                if isinstance(history, list):
                    return history
        except json.JSONDecodeError:
            print(f"[Warning] Chat history file is corrupt. Starting fresh.")
    
    # Return a fresh history, starting with the system prompt
    return [{'role': 'system', 'content': NEXO_COMMAND_PROMPT}] # Use the COMMAND prompt

def save_chat_history(history):
    """Saves the chat history list to the JSON file."""
    try:
        with open(CHAT_HISTORY_FILE, 'w') as f:
            json.dump(history, f, indent=2)
    except Exception as e:
        print(f"[Error] Could not save chat history: {e}")

# 6. Main Chat Loop
def main_chat_loop():
    print("--- Nexo AI Chatbot (Voice-to-Voice) ---")
    print(f"Using model: {MODEL_NAME}")
    print(f"Loading history from: {CHAT_HISTORY_FILE}")
    print("Say 'quit' or 'exit' to stop.")
    print("--------------------------------------")
    
    # --- PROMPT 1: The "SMART" JSON prompt for commands ---
    global NEXO_COMMAND_PROMPT 
    NEXO_COMMAND_PROMPT = f"""You are Nexo, a helpful and empathetic voice assistant that controls the computer.
Your job is to classify the user's prompt into one or more actions.
You must respond *only* with a single, valid JSON object. Do not add any other text.
All spoken text (in 'confirmation' or 'response' fields) MUST be 500 characters or less. Be concise.
You have a memory (the chat history). Use this memory to understand the current context.

ACTIONS:
1. "open_application": The user wants to open an application.
2. "type_string": The user wants to type text.
3. "click_text": The user wants to find and click text on the screen.
4. "key_press": The user wants to press a single key.
5. "key_combination": The user wants to press a hotkey (e.g., Ctrl+C).
6. "scroll": The user wants to scroll up or down.
7. "open_breathing_exercise": The user is stressed, sad, or anxious.
8. "open_url": The user wants to open a specific website.
9. "move_center": The user wants to move the mouse to the center.
10. "click_mouse": The user wants to click the mouse (at its current position).
11. "chat": The user is just chatting or asking a general question.

JSON FORMAT:
You MUST return a JSON object. It can be a single action OR a list of actions.

- **Single Action (Simple):**
{{"action": "open_application", "app_name": "Spotify", "confirmation": "Opening Spotify."}}

- **Multiple Actions (Complex):**
{{"actions": [
    {{"action": "open_application", "app_name": "Google Chrome", "confirmation": "Okay, opening Google Chrome."}},
    {{"action": "click_text", "text": "Downloads", "confirmation": "and clicking Downloads."}}
]}}

- **Simple "Chat" Action:**
{{"action": "chat", "response": "I am doing well, thank you for asking!"}}

---
**COMPLEX & EMPATHY RULES (VERY IMPORTANT):**

1.  **Empathy Rule:** If the user sounds stressed, sad, or tired, you MUST trigger a *chain* of actions (use the complex "actions" list format).
    * First, a "chat" action with a kind, supportive message (around 80 chars).
    * Second, the "open_breathing_exercise" action.
    * Third, an "open_url" action for the relaxing music: `{RELAX_URL}`

    **User:** "I am so stressed right now."
    **You:**
    {{"actions": [
        {{"action": "chat", "response": "I'm sorry to hear that. Please take a moment to relax. I'm opening a breathing exercise and some music for you."}},
        {{"action": "open_breathing_exercise"}},
        {{"action": "open_url", "url": "{RELAX_URL}"}}
    ]}}

2.  **Context Rule:** If the user just opened "File Explorer" and says "go to downloads", use the `type_string` action with `"press_enter": true`.

3.  **Spelling Rule:** You MUST correct spelling for `click_text`. If they say "click dwonlaods", you use `"text": "Downloads"`.
"""
    
    # --- PROMPT 2: The "SIMPLE" prompt for chatting ---
    global NEXO_CHAT_PROMPT
    NEXO_CHAT_PROMPT = (
        "You are Nexo, a helpful voice assistant. "
        "Your answers must ALWAYS be very short and concise (500 characters max). "
        "Keep your responses to one or two sentences maximum. "
        "Be direct and to the point. Do not use formatting like lists or markdown."
    )
    # --- END OF NEW PROMPTS ---

    
    # --- Load command history ---
    messages = load_chat_history()
    if not messages or messages[0].get('role') != 'system':
        print("[Warning] Invalid history, starting fresh.")
        messages = [{'role': 'system', 'content': NEXO_COMMAND_PROMPT}]
    else:
        messages[0]['content'] = NEXO_COMMAND_PROMPT 

    speak("Nexo is online and ready.")

    while True:
        prompt = listen_for_command()

        if not prompt:
            continue # Listen again if no speech was detected

        prompt_lower = prompt.lower()
        if prompt_lower in ['quit', 'exit', 'stop listening']:
            speak("Goodbye!")
            break
        
        print("\n[Nexo is thinking...]")
        
        # --- NEW LOGIC: Check for command word ---
        is_command = False
        for word in COMMAND_TRIGGER_WORDS:
            if prompt_lower.startswith(word):
                is_command = True
                break
        
        # --- SPECIAL CASE: Handle "I am stressed" ---
        if "stress" in prompt_lower or "sad" in prompt_lower or "anxious" in prompt_lower or "tired" in prompt_lower:
             is_command = True
        # --- END NEW LOGIC ---

        try:
            if is_command:
                # --- 1. RUN "SMART" COMMAND AI ---
                print("[Mode: Smart AI]")
                
                # Append user prompt to history
                messages.append({'role': 'user', 'content': prompt})
                
                # --- "short-term memory" window ---
                HISTORY_WINDOW_SIZE = 4 
                system_prompt = messages[0] 
                recent_history = messages[-HISTORY_WINDOW_SIZE:]
                messages_for_api = [system_prompt] + recent_history
                print(f"[Context] Sending {len(messages_for_api)} messages to AI (System + last {HISTORY_WINDOW_SIZE}).")
                # ---
                
                response = client.chat(
                    model=MODEL_NAME,
                    messages=messages_for_api, # <-- Use the short-term window
                    stream=False
                )
                
                reply_text = response['message']['content']
                
                # Append AI response to full history
                messages.append({'role': 'assistant', 'content': reply_text})
                save_chat_history(messages)

                # --- ACTION HANDLER STEP ---
                try:
                    print(f"[AI Raw Response]: {reply_text}")
                    action_data = json.loads(reply_text)
                    
                    # --- MODIFIED: Handle both simple and complex AI responses ---
                    actions_list = [] # Initialize an empty list
                    
                    if "actions" in action_data:
                        # This is the correct, multi-action format
                        actions_list = action_data.get("actions", [])
                    elif "action" in action_data:
                        # This is the simple, single-action format the AI is using
                        print("[Warning] AI returned simple format. Accepting it.")
                        actions_list = [action_data] # We put the *entire* dictionary into a list
                    # --- END MODIFICATION ---

                    if not actions_list:
                        print("[Warning] AI returned empty actions list.")
                        speak("Sorry, I'm not sure what to do.")
                        continue

                    for action_item in actions_list:
                        action = action_item.get("action")
                        
                        if action == "type_string":
                            text_to_type = action_item.get("text", "")
                            press_enter = action_item.get("press_enter", False)
                            speak(action_item.get("confirmation"))
                            if not safe_type_string(text_to_type, press_enter):
                                speak("Sorry, I had an error while typing.")

                        elif action == "open_application":
                            app_name = action_item.get("app_name", "")
                            speak(action_item.get("confirmation"))
                            if app_name:
                                if not safe_open_app(app_name):
                                    speak(f"Sorry, I had an error opening {app_name}.")
                            else:
                                speak("Sorry, I didn't catch which application to open.")

                        elif action == "click_text":
                            text_to_click = action_item.get("text", "")
                            speak(action_item.get("confirmation"))
                            if text_to_click:
                                if not safe_click_text(text_to_click):
                                    speak(f"Sorry, I couldn't find or click on '{text_to_click}'.")
                            else:
                                speak("Sorry, I didn't catch what you wanted to click on.")

                        elif action == "key_press":
                            key = action_item.get("key")
                            speak(action_item.get("confirmation"))
                            if key:
                                if not safe_key_press(key):
                                    speak("Sorry, I had an error pressing that key.")
                            else:
                                speak("Sorry, I didn't catch which key to press.")

                        elif action == "key_combination":
                            keys = action_item.get("keys")
                            speak(action_item.get("confirmation"))
                            if keys and isinstance(keys, list):
                                if not safe_key_combination(keys):
                                    speak("Sorry, I had an error with that hotkey.")
                            else:
                                speak("Sorry, I didn't catch which hotkey to use.")

                        elif action == "scroll":
                            direction = action_item.get("direction")
                            speak(action_item.get("confirmation"))
                            if direction in ["up", "down"]:
                                if not safe_scroll(direction):
                                    speak("Sorry, I had an error while scrolling.")
                            else:
                                speak("Sorry, I didn't catch which way to scroll.")

                        # --- NEW ACTION HANDLERS ---
                        elif action == "open_breathing_exercise":
                            speak(action_item.get("confirmation")) # AI might say "opening exercise"
                            if not safe_open_breathing_exercise():
                                speak("Sorry, I had an error opening the breathing exercise.")

                        elif action == "open_url":
                            url = action_item.get("url")
                            speak(action_item.get("confirmation"))
                            if url:
                                if not safe_open_url(url):
                                    speak("Sorry, I had an error opening that URL.")
                            else:
                                speak("Sorry, I didn't catch which URL to open.")
                        # --- END NEW HANDLERS ---

                        elif action == "move_center":
                            speak(action_item.get("confirmation"))
                            if not safe_move_center():
                                speak("Sorry, I had an error moving the mouse.")
                        
                        elif action == "click_mouse":
                            speak(action_item.get("confirmation"))
                            if not safe_click():
                                speak("Sorry, I had an error while clicking.")

                        elif action == "chat":
                            speak(action_item.get("response"))
                        
                        else:
                            print(f"[Warning] AI returned unknown action: {action}")
                            speak("I understood you, but I'm not sure what action to take.")

                except json.JSONDecodeError:
                    print(f"[Warning] AI did not return valid JSON. Speaking raw text.")
                    speak(reply_text)
                    messages.pop() 
                    save_chat_history(messages)
            
            else:
                # --- 2. RUN "SIMPLE" CHATBOT AI ---
                print("[Mode: Simple Chat]")
                response = client.chat(
                    model=MODEL_NAME,
                    messages=[
                        {'role': 'system', 'content': NEXO_CHAT_PROMPT},
                        {'role': 'user', 'content': prompt}
                    ],
                    stream=False
                )
                
                reply_text = response['message']['content']
                speak(reply_text)
            
            # --- END OF IF/ELSE BLOCK ---

        except ollama.ResponseError as e:
            error_message = f"OLLAMA ERROR: {e.error}"
            print(f"\n❌ {error_message}")
            if "model" in e.error and "not found" in e.error:
                speak(f"Error: The model named {MODEL_NAME} was not found.")
                print(f"   You must first pull the model: ollama pull {MODEL_NAME}")
                break 
        except Exception as e:
            error_message = f"An unexpected error occurred: {e}"
            print(f"\n❌ {error_message}")
            speak("Sorry, I ran into an unexpected error.")
            break

# --- Run the main chat loop ---
if __name__ == "__main__":
    main_chat_loop()