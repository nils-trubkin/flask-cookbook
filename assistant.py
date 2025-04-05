""" This script listens for the wake word 'Hey Cookbook' and then listens for a command. """

import os
import subprocess
import json
import requests

# import sqlite3
import pvporcupine
import pyaudio
import numpy as np
from dotenv import load_dotenv
from num2words import num2words as n2w
from vosk import Model, KaldiRecognizer
from word2number import w2n

load_dotenv()
os.environ["BROWSER"] = "chromium-browser"
os.environ["DISPLAY"] = ":0.0"
ACCESS_KEY = os.getenv("PICOVOICE_ACCESS_KEY")
WAKE_WORD_FILE = os.getenv("WAKE_WORD_FILE")
MODEL_FILE = os.getenv("MODEL_FILE")

# Absolute path to the database
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATABASE_PATH = f"{BASE_DIR}/recipes.db"
WAKE_WORD_PATH = os.path.join(BASE_DIR, f"wake_words/{WAKE_WORD_FILE}")
MODEL_PATH = os.path.join(BASE_DIR, f"models/{MODEL_FILE}")
LED_PATH = "/sys/class/leds/ACT/brightness"
INPUT_DEVICE_INDEX = 1


def led(state: int):
    """Turn the Raspberry Pi LED on or off"""
    try:
        subprocess.run(
            f"echo {state} | sudo tee {LED_PATH} > /dev/null", shell=True, check=True
        )
    except subprocess.CalledProcessError:
        error("Could not change LED state")


def push_notification(title: str, message: str):
    """Send a notification using dunst"""
    try:
        subprocess.run(
            ["dunstify", title, message, "-i", f"{BASE_DIR}/static/images/mic.png"],
            check=True,
        )
    except subprocess.CalledProcessError:
        error("Could not send notification")


def close_notifications():
    """Close all notifications using dunstctl"""
    try:
        subprocess.run(["dunstctl", "close-all"], check=True)
    except subprocess.CalledProcessError:
        error("Could not close notifications")


def xdg_open(url: str):
    """Open a URL in the default browser"""
    try:
        subprocess.run(["xdg-open", url], check=True)
    except subprocess.CalledProcessError:
        error("Could not open browser")


def scroll(direction: str):
    """Scroll the page up or down"""
    try:
        if direction == "up":
            subprocess.run(["xdotool", "key", "Page_Up"], check=True)
        elif direction == "down":
            subprocess.run(["xdotool", "key", "Page_Down"], check=True)
    except subprocess.CalledProcessError:
        error("Could not scroll")


# def get_recipes_size():
#     """Get the number of recipes in the database"""
#     try:
#         conn = sqlite3.connect(DATABASE_PATH)
#         cursor = conn.cursor()
#         cursor.execute("SELECT COUNT(*) FROM recipes")
#         recipes_size = cursor.fetchone()[0]
#     except sqlite3.OperationalError:
#         print("Error: Database not found")
#     finally:
#         conn.close()
#     return recipes_size


def get_grammar():
    """Get the grammar for Vosk"""
    # recipes_size = get_recipes_size()
    # All numbers 1-99 using num2word
    all_numbers = list(
        # {word for i in range(1, recipes_size + 1) for word in n2w(i).split("-")}
        {word for i in range(1, 100) for word in n2w(i).split("-")}
    )
    keywords = [
        "show",
        "all",
        "open",
        "recipe",
        "recipes",
        "number",
        "scroll",
        "up",
        "down",
        "timer",
    ]
    grammar = str(all_numbers + keywords).replace("'", '"')
    return grammar


def init():
    """Initialize Porcupine, PyAudio, and Vosk"""
    # Initialize Porcupine with your wake word
    porcupine = pvporcupine.create(
        access_key=ACCESS_KEY, keyword_paths=[WAKE_WORD_PATH]
    )

    # Set up PyAudio
    audio = pyaudio.PyAudio()

    # Initialize Vosk speech recognition model
    model = Model(MODEL_PATH)
    recognizer = KaldiRecognizer(model, 16000)
    grammar = get_grammar()
    recognizer.SetGrammar(grammar)

    # Open audio stream for microphone
    stream = audio.open(
        format=pyaudio.paInt16,
        channels=1,
        rate=16000,
        input=True,
        frames_per_buffer=4096,
        input_device_index=INPUT_DEVICE_INDEX,
    )
    stream.start_stream()

    print("Listening for 'Hey Cookbook'...")
    led(0)
    close_notifications()
    return porcupine, audio, stream, recognizer


def parse(result: str):
    """Parse the result from Vosk and execute the command"""
    # Pick out 'text' from json result
    result = json.loads(result).get("text", "")
    print(f"Recognized: {result}")
    close_notifications()
    push_notification("Recognized", result)
    if ("show" in result or "all" in result) and (
        "recipes" in result or "recipe" in result
    ):
        print("Showing all recipes")
        xdg_open("http://localhost:8001/grid")
    elif "number" in result:
        # Extract the first matching word from the result

        try:
            number = w2n.word_to_num(result)
        except ValueError:
            print(f"Could not convert '{result}' to a number")
        print(f"Showing recipe number {number}")
        # Execute in the background
        xdg_open(f"http://localhost:8001/recipes/{number}")
    elif "scroll" in result:
        if "up" in result:
            print("Scrolling up")
            scroll("up")
        elif "down" in result:
            print("Scrolling down")
            scroll("down")
    elif "timer" in result:
        duration = None
        try:
            duration = w2n.word_to_num(result)
            response = requests.post(
                "http://localhost:8001/commands",
                json={"action": "timer", "duration": duration},
                timeout=5,
            )
            print(response.status_code)
        except ValueError:
            print(f"Could not convert '{result}' to a number")
        except requests.exceptions.RequestException as e:
            print(f"Error: {e}")

            # Check if "stop" is in the result (for stopping the loop)
            # if "stop" in result.lower():
            #     print("Stopping.")
            #     break


def vosk_listen(stream, recognizer):
    """Listen for speech using Vosk"""
    # Once the wake word is detected, start speech recognition with Vosk
    while True:
        # Read the next audio chunk
        pcm = stream.read(4000, exception_on_overflow=False)
        if recognizer.AcceptWaveform(pcm):
            parse(recognizer.Result())
            led(0)
            close_notifications()
            break

        # Check partial result and print if available
        # else:
        #     partial_result = recognizer.PartialResult()
        #     print(f"Partial result: {partial_result}")


def error(message: str):
    """Print an error message, log the error in file"""
    print(message)
    push_notification("Error", message)
    with open("/var/log/assistant.log", "a", encoding="utf-8") as f:
        f.write(f"{message}\n")


def loop(porcupine, audio, stream, recognizer):
    """Listen for the wake word and then listen for a command"""
    try:
        while True:
            # Read audio data from the microphone (this should be 512 samples)
            pcm = stream.read(512, exception_on_overflow=False)
            pcm = np.frombuffer(pcm, dtype=np.int16)

            # Process the audio chunk with Porcupine
            keyword_index = porcupine.process(pcm)

            # If the keyword is detected, the index will be >= 0
            if keyword_index >= 0:
                print("Wake word detected! Listening for speech...")
                led(1)
                push_notification("Wake word detected", "Listening for command...")
                vosk_listen(stream, recognizer)

    finally:
        # Clean up resources
        stream.stop_stream()
        stream.close()
        audio.terminate()
        porcupine.delete()
        led(0)


if __name__ == "__main__":
    _porcupine, _audio, _stream, _recognizer = init()
    loop(_porcupine, _audio, _stream, _recognizer)
