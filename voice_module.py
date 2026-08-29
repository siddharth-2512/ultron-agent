import pyttsx3
import speech_recognition as sr

# Initialize Text-to-Speech Engine
tts_engine = pyttsx3.init()
tts_engine.setProperty('rate', 160)


def speak(text):
    """Converts text to spoken audio output."""
    print(f"[ULTRON Audio Output]: {text}")
    tts_engine.say(text)
    tts_engine.runAndWait()


def listen_command():
    """Captures audio from microphone and transcribes speech."""
    recognizer = sr.Recognizer()

    with sr.Microphone() as source:
        speak("Listening for staff command.")
        recognizer.adjust_for_ambient_noise(source, duration=1)
        audio = recognizer.listen(source)

        try:
            transcribed_text = recognizer.recognize_google(audio)
            print(f"[Staff Input Detected]: '{transcribed_text}'")
            return transcribed_text
        except sr.UnknownValueError:
            print("[ULTRON Audio Error]: Could not understand audio.")
            return ""
        except sr.RequestError as e:
            print(f"[ULTRON Audio Error]: Could not request results; {e}")
            return ""


if __name__ == "__main__":
    speak("ULTRON Audio Engine initialized.")
    command = listen_command()
    if command:
        speak(f"Command received: {command}")