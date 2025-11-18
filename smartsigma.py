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

# --- CONFIGURATION ---
MODEL_NAME = 'gemma3:1b'  # !! Change this if 'gemma3:1b' is not correct
OLLAMA_HOST_URL = "http://127.0.0.1:11434" # The server you specified
CHAT_HISTORY_FILE = 'chathistory.json' 
SCROLL_AMOUNT = 500 # Number of pixels to scroll per command
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
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

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

# --- NEW FUNCTION: Key Press ---
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

# --- NEW FUNCTION: Key Combination ---
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

# --- NEW FUNCTION: Scroll ---
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
# --- END NEW FUNCTIONS ---


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
    return [{'role': 'system', 'content': NEXO_SYSTEM_PROMPT}]

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
    
    # --- UPGRADED AI-DRIVEN SYSTEM PROMPT ---
    global NEXO_SYSTEM_PROMPT 
    NEXO_SYSTEM_PROMPT = """You are Nexo, a helpful voice assistant that can also control the computer.
Your job is to classify the user's prompt into one of the following actions.
You must respond *only* with a single, valid JSON object. Do not add any other text.
You have a memory (the chat history). Use this memory to understand the current context.

ACTIONS:
1. "type_string": The user wants to type text.
2. "open_application": The user wants to open an application.
3. "click_text": The user wants to find and click text on the screen.
4. "key_press": The user wants to press a single key.
5. "key_combination": The user wants to press a hotkey (e.g., Ctrl+C).
6. "scroll": The user wants to scroll up or down.
7. "move_center": The user wants to move the mouse to the center.
8. "click_mouse": The user wants to click the mouse (at its current position).
9. "chat": The user is just chatting or asking a question.

JSON FORMAT:
- Type string:
{"action": "type_string", "text": "text to type", "press_enter": false, "confirmation": "Okay, typing that."}

- Open application:
{"action": "open_application", "app_name": "Google Chrome", "confirmation": "Okay, opening Google Chrome."}

- Click text on screen:
{"action": "click_text", "text": "Downloads", "confirmation": "Okay, clicking on 'Downloads'."}
(You MUST correct spelling. If they say "dwonlaods", you must use "Downloads".)

- Key press:
{"action": "key_press", "key": "enter", "confirmation": "Pressing enter."}
(Common keys: 'enter', 'esc', 'tab', 'f5', 'delete', 'backspace')

- Key combination:
{"action": "key_combination", "keys": ["ctrl", "c"], "confirmation": "Copying to clipboard."}
(Common keys: 'ctrl', 'alt', 'shift', 'win', 'cmd')

- Scroll:
{"action": "scroll", "direction": "down", "confirmation": "Scrolling down."}
(Directions: "up" or "down")

- Move center:
{"action": "move_center", "confirmation": "Moving mouse to center."}

- Click mouse:
{"action": "click_mouse", "confirmation": "Clicking."}

- Chat:
{"action": "chat", "response": "This is where your normal answer goes."}

---
**CONTEXT & HOTKEY RULES:**
1.  **Context:** If the user just opened "File Explorer" and says "go to downloads", use the `type_string` action with "press_enter": true.
2.  **Hotkeys:** Map common phrases to hotkeys. "Copy" -> ["ctrl", "c"]. "Paste" -> ["ctrl", "v"]. "Save" -> ["ctrl", "s"]. "Undo" -> ["ctrl", "z"].
3.  **Spelling:** Always correct spelling for `click_text`.

Example 1:
User: "Open File Explorer"
You: {"action": "open_application", "app_name": "File Explorer", "confirmation": "Opening File Explorer."}
User: "Okay, now go to the downloads folder"
You: {"action": "type_string", "text": "downloads", "press_enter": true, "confirmation": "Okay, going to downloads."}

Example 2:
User: "scroll down"
You: {"action": "scroll", "direction": "down", "confirmation": "Scrolling down."}

Example 3:
User: "please copy that"
You: {"action": "key_combination", "keys": ["ctrl", "c"], "confirmation": "Copying."}
"""
    
    # --- MODIFIED: Load history at start ---
    messages = load_chat_history()
    # If history is not empty and first message is system, use it.
    # Otherwise, reset history.
    if not messages or messages[0].get('role') != 'system':
        print("[Warning] Invalid history, starting fresh.")
        messages = [{'role': 'system', 'content': NEXO_SYSTEM_PROMPT}]
    else:
        # Ensure the *current* system prompt is what's in memory
        messages[0]['content'] = NEXO_SYSTEM_PROMPT 

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
        
        # --- MODIFIED: Append user prompt to history ---
        messages.append({'role': 'user', 'content': prompt})
        
        try:
            # --- AI CLASSIFICATION STEP ---
            response = client.chat(
                model=MODEL_NAME,
                messages=messages, # <-- Pass the entire chat history
                stream=False
            )
            
            reply_text = response['message']['content']
            
            # --- MODIFIED: Append AI response to history ---
            messages.append({'role': 'assistant', 'content': reply_text})
            # Save history *after* AI responds
            save_chat_history(messages)

            # --- ACTION HANDLER STEP ---
            try:
                # The AI *should* return JSON. We try to parse it.
                print(f"[AI Raw Response]: {reply_text}")
                action_data = json.loads(reply_text)
                action = action_data.get("action")
                
                if action == "type_string":
                    text_to_type = action_data.get("text", "")
                    # --- MODIFIED: Check for 'press_enter' ---
                    press_enter = action_data.get("press_enter", False)
                    speak(action_data.get("confirmation", f"Typing: {text_to_type}"))
                    
                    if not safe_type_string(text_to_type, press_enter):
                        speak("Sorry, I had an error while typing.")

                elif action == "open_application":
                    app_name = action_data.get("app_name", "")
                    confirmation = action_data.get("confirmation", f"Opening {app_name}.")
                    
                    if app_name:
                        speak(confirmation)
                        if not safe_open_app(app_name):
                            speak(f"Sorry, I had an error opening {app_name}.")
                    else:
                        speak("Sorry, I didn't catch which application to open.")

                elif action == "click_text":
                    text_to_click = action_data.get("text", "")
                    confirmation = action_data.get("confirmation", f"Clicking on {text_to_click}.")
                    
                    if text_to_click:
                        speak(confirmation)
                        if not safe_click_text(text_to_click):
                            speak(f"Sorry, I couldn't find or click on '{text_to_click}'.")
                    else:
                        speak("Sorry, I didn't catch what you wanted to click on.")

                # --- NEW ACTION HANDLERS ---
                elif action == "key_press":
                    key = action_data.get("key")
                    if key:
                        speak(action_data.get("confirmation", f"Pressing {key}."))
                        if not safe_key_press(key):
                            speak("Sorry, I had an error pressing that key.")
                    else:
                        speak("Sorry, I didn't catch which key to press.")

                elif action == "key_combination":
                    keys = action_data.get("keys")
                    if keys and isinstance(keys, list):
                        speak(action_data.get("confirmation", "Performing hotkey."))
                        if not safe_key_combination(keys):
                            speak("Sorry, I had an error with that hotkey.")
                    else:
                        speak("Sorry, I didn't catch which hotkey to use.")

                elif action == "scroll":
                    direction = action_data.get("direction")
                    if direction in ["up", "down"]:
                        speak(action_data.get("confirmation", f"Scrolling {direction}."))
                        if not safe_scroll(direction):
                            speak("Sorry, I had an error while scrolling.")
                    else:
                        speak("Sorry, I didn't catch which way to scroll.")
                # --- END NEW ACTION HANDLERS ---

                elif action == "move_center":
                    speak(action_data.get("confirmation", "Moving mouse."))
                    if not safe_move_center():
                        speak("Sorry, I had an error moving the mouse.")
                
                elif action == "click_mouse":
                    speak(action_data.get("confirmation", "Clicking."))
                    if not safe_click():
                        speak("Sorry, I had an error while clicking.")

                elif action == "chat":
                    # This is a normal chat response
                    speak(action_data.get("response", "I'm not sure what to say."))
                
                else:
                    print(f"[Warning] AI returned unknown action: {action}")
                    speak("I understood you, but I'm not sure what action to take.")

            except json.JSONDecodeError:
                # If the AI response wasn't valid JSON, it's probably
                # a small model failing. We just speak the raw text.
                print(f"[Warning] AI did not return valid JSON. Speaking raw text.")
                speak(reply_text)
                # --- MODIFIED: Remove the bad JSON from history ---
                messages.pop() # Remove the last assistant message
                save_chat_history(messages) # Re-save

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