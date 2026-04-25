import ollama
import pyttsx3
import speech_recognition as sr
import sys
import webbrowser        
import urllib.parse      

# --- CONFIGURATION ---
MODEL_NAME = 'gemma3:1b'  # !! Change this if 'gemma3:1b' is not correct
OLLAMA_HOST_URL = "http://127.0.0.1:11434" # The server you specified
# --- END CONFIGURATION ---

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

# 5. Main Chat Loop
def main_chat_loop():
    """
    Main loop to chat with Nexo via voice.
    """
    print("--- Nexo AI Chatbot (Voice-to-Voice) ---")
    print(f"Using model: {MODEL_NAME}")
    print("Say 'quit' or 'exit' to stop.")
    print("--------------------------------------")
    
    # --- MODIFIED: SYSTEM PROMPT (GAVE AI A "TOOL") ---
    NEXO_SYSTEM_PROMPT = (
        "You are Nexo, a helpful voice assistant. "
        "Your answers must ALWAYS be very short and concise. "
        "Keep your responses to one or two sentences maximum. "
        "Be direct and to the point. Do not use formatting. "
        "---"
        "TOOLS:"
        "If the user asks you to open a website, search for something, or go to a URL, "
        "you must respond *only* with the text 'NEXO_OPEN: [full_url]'."
        "Example: If the user says 'open YouTube', you must respond with 'NEXO_OPEN: https://www.youtube.com'. "
        "Example: If the user says 'search for dogs', you must respond with 'NEXO_OPEN: https://www.google.com/search?q=dogs'. "
        "Use your memory to figure out URLs. If the user says 'open my favorite site' and they "
        "previously told you their favorite site is Instructables, you must respond with 'NEXO_OPEN: https://www.instructables.com'."
    )
    # --- END OF MODIFICATION ---
    
    chat_history = [
        {'role': 'system', 'content': NEXO_SYSTEM_PROMPT}
    ]

    intro_message = (
        "Hello, I’m Nexo. "
        "I’m your personal assistant who looks after your mind, your schedule, and your stress. "
        "I can read your ECG signals to quietly sense when you’re tense and help calm you down. "
        "I work completely offline, so everything you share stays safe with me. "
        "Whether you're studying, working, or just trying to breathe a little easier—I’m right here with you."
    )
    speak(intro_message)

    while True:
        prompt = listen_for_command()

        if prompt:
            prompt_lower = prompt.lower() 

            if prompt_lower in ['quit', 'exit']:
                speak("Goodbye!")
                break
            
            # --- We keep these "play" commands for speed ---
            elif 'play' in prompt_lower and 'on youtube' in prompt_lower:
                search_term = prompt_lower.partition('play')[-1].partition('on youtube')[0].strip()
                if search_term:
                    speak(f"Searching YouTube for {search_term}")
                    search_url = f"https://www.youtube.com/results?search_query={urllib.parse.quote(search_term)}"
                    webbrowser.open_new_tab(search_url)
                else:
                    speak("Sorry, what would you like me to play on YouTube?")
            
            elif 'play' in prompt_lower and 'on spotify' in prompt_lower:
                search_term = prompt_lower.partition('play')[-1].partition('on spotify')[0].strip()
                if search_term:
                    speak(f"Searching Spotify for {search_term}")
                    search_url = f"https://open.spotify.com/search/{urllib.parse.quote(search_term)}"
                    webbrowser.open_new_tab(search_url)
                else:
                    speak("Sorry, what would you like me to play on Spotify?")

            # --- DELETED: The "elif 'open'..." block is GONE. ---
            # The AI will handle it now.

            # --- IF NO COMMAND MATCHES, SEND TO OLLAMA (AI chat) ---
            else:
                print("\n[Nexo is thinking...]")
                
                chat_history.append({'role': 'user', 'content': prompt})

                try:
                    response = client.chat(
                        model=MODEL_NAME,
                        messages=chat_history, 
                        stream=False
                    )
                    
                    reply_text = response['message']['content'].strip()
                    
                    # --- MODIFIED: Check if the AI wants to use its "TOOL" ---
                    if reply_text.startswith("NEXO_OPEN:"):
                        url_to_open = reply_text.partition('NEXO_OPEN:')[-1].strip()
                        speak(f"Opening that for you.")
                        webbrowser.open_new_tab(url_to_open)
                        
                        # Add what *happened* to memory, not the command
                        chat_history.append({'role': 'assistant', 'content': f"I have opened {url_to_open} for the user."})
                    
                    else:
                        # This is a normal chat message
                        chat_history.append({'role': 'assistant', 'content': reply_text})
                        speak(reply_text)
                    # --- END OF MODIFICATION ---

                except ollama.ResponseError as e:
                    error_message = f"OLLAMA ERROR: {e.error}"
                    print(f"\n❌ {error_message}")
                    speak("Sorry, I had an error with the AI model.")
                    chat_history.pop() 
                    if "model" in e.error and "not found" in e.error:
                        speak(f"Error: The model named {MODEL_NAME} was not found.")
                        print(f"   You must first pull the model: ollama pull {MODEL_NAME}")
                        break 
                except Exception as e:
                    error_message = f"An unexpected error occurred: {e}"
                    print(f"\n❌ {error_message}")
                    speak("Sorry, I ran into an unexpected error.")
                    chat_history.pop() 
                    break

# --- Run the main chat loop ---
if __name__ == "__main__":
    main_chat_loop()
