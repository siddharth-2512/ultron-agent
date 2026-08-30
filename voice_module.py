import re
import pyttsx3
import speech_recognition as sr
import threading
import asyncio

class VoiceEngineWrapper:
    """Wrapper to handle pyttsx3 calls safely in background threads without blocking video streams."""
    
    def _speak_worker(self, text: str):
        """Worker thread function to isolate pyttsx3 initialization and execution."""
        try:
            # Re-initialize engine per-thread to avoid COM / SAPI5 thread concurrency crashes on Windows
            engine = pyttsx3.init()
            engine.setProperty('rate', 165)
            voices = engine.getProperty('voices')
            if voices:
                engine.setProperty('voice', voices[0].id)
            
            engine.say(text)
            engine.runAndWait()
            engine.stop()
        except Exception as e:
            print(f"[TTS ERROR] {e}")

    def speak(self, text: str):
        if not text:
            return
        
        # Clean Markdown formatting (*, #, _, etc.) for clean speech
        clean_text = re.sub(r'[*_#`~]', '', text)
        
        # Dispatch TTS to a non-blocking daemon thread
        threading.Thread(target=self._speak_worker, args=(clean_text,), daemon=True).start()

    def say(self, text: str):
        self.speak(text)


# Export voice_engine instance
voice_engine = VoiceEngineWrapper()


def listen_command() -> str:
    """Blocking microphone listener. Call via listen_command_async from async endpoints."""
    recognizer = sr.Recognizer()
    recognizer.dynamic_energy_threshold = True
    
    try:
        with sr.Microphone() as source:
            recognizer.adjust_for_ambient_noise(source, duration=0.5)
            audio = recognizer.listen(source, timeout=4, phrase_time_limit=6)
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


async def listen_command_async() -> str:
    """Non-blocking async wrapper for speech recognition."""
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, listen_command)


def log_query(query_text: str, response_text: str = "", log_callback=None):
    if log_callback and query_text:
        log_callback(f"[Voice Input]: {query_text}")
    if response_text:
        voice_engine.speak(response_text)