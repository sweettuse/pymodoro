from pathlib import Path
import simpleaudio as sa


def play():
    fname = f"{Path(__file__).parent}/TADA.WAV"
    sa.WaveObject.from_wave_file(fname).play()
