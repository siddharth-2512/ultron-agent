import speech_recognition as sr
import pyttsx3
import speech_recognition as sr
import pyttsx3

# Initialize TTS Engine
engine = pyttsx3.init()

def speak(text):
    """Re-initialized engine call to avoid pyttsx3 thread-locking bug."""
    try:
        engine = pyttsx3.init()
        engine.setProperty("rate", 160)
        engine.setProperty("volume", 1.0)
        engine.say(text)
        engine.runAndWait()
        engine.stop()
    except Exception as e:
        print(f"[TTS Error]: {e}")

def listen_command():
    """Tuned SpeechRecognition for crisp, fast capture."""
    r = sr.Recognizer()
    
    # Prevents listening indefinitely or picking up background hums
    r.dynamic_energy_threshold = True
    r.energy_threshold = 300  # Adjust baseline noise threshold
    r.pause_threshold = 0.8   # Wait 0.8s of silence before concluding speech

    with sr.Microphone() as source:
        # Quick ambient calibration
        r.adjust_for_ambient_noise(source, duration=0.5)
        try:
            # 5-second max wait to start speaking, 7-second max speech duration
            audio = r.listen(source, timeout=5, phrase_time_limit=7)
            command = r.recognize_google(audio)
            return command
        except (sr.WaitTimeoutError, sr.UnknownValueError):
            return None
        except sr.RequestError as e:
            print(f"[STT API Error]: {e}")
            return None