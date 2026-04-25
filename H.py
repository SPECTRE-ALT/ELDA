import ollama
import pyttsx3
import speech_recognition as sr
import sys

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

# 3. Text-to-Speech (TTS) Function (NOT TOUCHED)
def speak(text):
    """
    Prints the text and speaks it using the TTS engine.
    
    *** FIX: We initialize the engine *inside* the function. ***
    This prevents conflicts with the speech_recognition library.
    """
    print(f"\n🤖 Nexo:")
    print(text)
    try:
        # Initialize the engine fresh *every time*
        engine = pyttsx3.init()
        engine.say(text)
        engine.runAndWait()
        
        # We no longer need to manually stop, as it's a new instance.
        # engine.stop() 
        
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
    
    # --- MODIFICATION (PART 1): ADDED SYSTEM PROMPT ---
    # This tells the model *how* to behave.
    NEXO_SYSTEM_PROMPT = (
        "You are Nexo, a helpful voice assistant. "
        "Your answers must ALWAYS be very short and concise. "
        "Keep your responses to one or two sentences maximum. "
        "Be direct and to the point. Do not use formatting like lists or markdown."
    )
    # --- END OF MODIFICATION (PART 1) ---
    
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
            if prompt.lower() in ['quit', 'exit']:
                speak("Goodbye!")
                break
            
            print("\n[Nexo is thinking...]")

            try:
                # --- MODIFICATION (PART 2): UPDATED client.chat() ---
                # We send the system prompt *before* the user's prompt.
                response = client.chat(
                    model=MODEL_NAME,
                    messages=[
                        {'role': 'system', 'content': NEXO_SYSTEM_PROMPT},
                        {'role': 'user', 'content': prompt}
                    ],
                    stream=False
                )
                # --- END OF MODIFICATION (PART 2) ---
                
                reply_text = response['message']['content']
                speak(reply_text)

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
