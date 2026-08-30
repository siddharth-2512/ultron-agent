import re
import pyttsx3
import speech_recognition as sr

class VoiceEngineWrapper:
    """Wrapper to handle pyttsx3 calls safely across threads and expose .speak() / .say()"""
    def speak(self, text: str):
        if not text:
            return
        
        # Strip Markdown formatting (*, #, _, etc.) so speech sounds clean
        clean_text = re.sub(r'[*_#`~]', '', text)
        
        try:
            engine = pyttsx3.init()
            engine.setProperty('rate', 165)
            voices = engine.getProperty('voices')
            if voices:
                engine.setProperty('voice', voices[0].id)
            
            engine.say(clean_text)
            engine.runAndWait()
            engine.stop()
        except Exception as e:
            print(f"[TTS ERROR] {e}")

    def say(self, text: str):
        self.speak(text)

# Export voice_engine so line 19 in main.py succeeds
voice_engine = VoiceEngineWrapper()

def listen_command() -> str:
    recognizer = sr.Recognizer()
    recognizer.dynamic_energy_threshold = True
    
    try:
        with sr.Microphone() as source:
            recognizer.adjust_for_ambient_noise(source, duration=0.5)
            audio = recognizer.listen(source, timeout=5, phrase_time_limit=8)
            text = recognizer.recognize_google(audio)
            return text.lower()
    except sr.WaitTimeoutError:
        print("[VOICE] Listening timed out.")
        return ""
    except sr.UnknownValueError:
        print("[VOICE] Could not parse speech.")
        return ""
    except Exception as e:
        print(f"[VOICE ERROR] {e}")
        return ""

def log_query(query_text: str, response_text: str = "", log_callback=None):
    if log_callback and query_text:
        log_callback(f"[Voice Input]: {query_text}")
    if response_text:
        voice_engine.speak(response_text)