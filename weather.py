import os
import subprocess
from dotenv import load_dotenv

class Weather:
    def __init__(self):
        load_dotenv()
        self.weather_url = os.getenv("WEATHER_URL")

        if not self.weather_url:
            raise ValueError("WEATHER_URL is missing in your .env file")

    def open(self):
        """
        Opens the weather URL in the default system browser
        using xdg-open (Linux).
        """
        try:
            subprocess.Popen(["xdg-open", self.weather_url])
        except Exception as e:
            print(f"Failed to open weather URL: {e}")

