import os
import time
import threading
from Features.Alert import Alert
from TextToSpeech.Fast_DF_TTS import speak_blocking
from Time_operations.time_manager import input_manage,input_manage_Alam,parse_input_Alarm,parse_input
from os import getcwd


def load_schedule(file_path):
    schedule = {}
    try:
        with open(file_path, 'r') as file:
            for line in file:
                if '=' in line:
                    line_time, activity = line.strip().split(' = ')
                    schedule[line_time.strip()] = activity.strip()
    except Exception as e:
        print(f"Error loading schedule: {e}")
    return schedule

def check_schedule(file_path):
    last_modified = 0
    while True:
        current_time = time.strftime("%I:%M%p")
        try:
            # Check file modification time
            modified = os.path.getmtime(file_path)
            if modified != last_modified:
                last_modified = modified
                schedule = load_schedule(file_path)

            if current_time in schedule:
                text = schedule[current_time]
                speak_blocking(text)
                Alert(text)

        except Exception as e:
            print(f"Error: {e}")

        time.sleep(60)



def load_Alam_Time(file_path):
    schedule = {}
    try:
        with open(file_path, 'r') as file:
            schedule= file.read()
    except Exception as e:
        print(f"Error loading schedule: {e}")
    return schedule


# Alam_path is passed as a parameter to check_Alam() — no global needed.

def check_Alam(Alam_path):
    last_modified = 0
    while True:
        current_time = time.strftime("%I:%M%p")
        try:
            # Check file modification time
            modified = os.path.getmtime(Alam_path)
            if modified != last_modified:
                last_modified = modified
                schedule = load_Alam_Time(Alam_path)

            if current_time in schedule:
                text = "This is Alarm"
                speak_blocking(text)
                Alert(text)

        except Exception as e:
            print(f"Error: {e}")

        time.sleep(10)