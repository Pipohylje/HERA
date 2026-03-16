import re
import requests
import json
import os
import time
from config import *


VALID_COMMANDS = [
    "USE_AVATAR",
    "WALK",
    "TURN",
    "SPEAK"
]

def normalize_line(line):
    line = line.replace("'", '"').strip()
    #print(f"[normalize_line] Input: {line}")

    # SPEAK: hello
    m = re.match(r"SPEAK\s*:\s*(.*)", line, re.IGNORECASE)
    if m:
        text = m.group(1).strip()
        result = f'SPEAK("{text}")'
        #print(f"[normalize_line] Matched SPEAK: {result}")
        return result

    # SPEAK hello
    m = re.match(r"SPEAK\s+(.*)", line, re.IGNORECASE)
    if m and "(" not in line:
        text = m.group(1).strip()
        result = f'SPEAK("{text}")'
        #print(f"[normalize_line] Matched SPEAK no parentheses: {result}")
        return result

    # WALK forward 1.0
    m = re.match(r"WALK\s+(\w+)\s+([\d\.]+)", line, re.IGNORECASE)
    if m:
        result = f"WALK({m.group(1)}, {m.group(2)})"
        #print(f"[normalize_line] Matched WALK: {result}")
        return result

    # TURN 30
    m = re.match(r"TURN\s+([\d\.]+)", line, re.IGNORECASE)
    if m:
        result = f"TURN({m.group(1)})"
        #print(f"[normalize_line] Matched TURN: {result}")
        return result

    # USE_AVATAR hero
    m = re.match(r"USE_AVATAR\s+([\w\-]+)", line, re.IGNORECASE)
    if m and "(" not in line:
        avatar = m.group(1).strip()
        result = f'USE_AVATAR("{avatar}")'
        #print(f"[normalize_line] Matched USE_AVATAR: {result}")
        return result

    #print(f"[normalize_line] No normalization applied.")
    return line

def extract_commands(text):
    commands = []

    lines = text.split("\n")
    print(f"[extract_commands] Total lines: {len(lines)}")

    for line_no, line in enumerate(lines, start=1):
        line = line.strip()
        if not line:
            continue

        #print(f"[extract_commands] Line {line_no}: {line}")
        line = normalize_line(line)
        #print(f"[extract_commands] Normalized Line {line_no}: {line}")

        # Extract all COMMAND(...) patterns
        pattern = r'\b([A-Z_]+)\s*\(([^)]*)\)'
        matches = list(re.finditer(pattern, line, re.IGNORECASE))

        #print(f"[extract_commands] Found {len(matches)} matches on line {line_no}")

        for match_no, match in enumerate(matches, start=1):
            cmd = match.group(1).upper()
            full_cmd = match.group(0)
            #print(f"[extract_commands] Match {match_no}: cmd='{cmd}', full='{full_cmd}'")

            if cmd in VALID_COMMANDS:
                commands.append(full_cmd)
                print(f"[extract_commands] Added command: {full_cmd}")
            else:
                print(f"[extract_commands] Ignored command: {full_cmd}")

    print(f"[extract_commands] Total commands extracted: {len(commands)}")
    return commands

def load_system_prompt():
    with open(SYSTEM_PROMPT_FILE, "r", encoding="utf-8") as f:
        return f.read()

def load_memory():

    if not os.path.exists(MEMORY_FILE):
        return []

    try:
        with open(MEMORY_FILE, "r") as f:
            data = json.load(f)

        # ensure memory is a list
        if isinstance(data, list):
            return data
        else:
            print("Memory file corrupted. Resetting.")
            return []

    except Exception as e:
        print("Failed to load memory:", e)
        return []

def save_memory(memory):
    with open(MEMORY_FILE, "w") as f:
        json.dump(memory, f, indent=2)

def trim_memory(memory):
    if len(memory) > MAX_MEMORY_MESSAGES:
        return memory[-MAX_MEMORY_MESSAGES:]
    return memory

def ollama_chat(model, messages):

    payload = {
        "model": model,
        "messages": messages,
        "stream": False
    }

    r = requests.post(OLLAMA_URL, json=payload)
    r.raise_for_status()

    return r.json()["message"]["content"]

def summarize_state(state_json):

    messages = [
        {
            "role": "system",
            "content": "Describe the important details in the JSON as a roleplay setting. Keep it relatively short. Do not invent details."
        },
        {
            "role": "user",
            "content": json.dumps(state_json)
        }
    ]

    return ollama_chat(SUMMARY_MODEL, messages)

def read_state_file():

    if not os.path.exists(STATE_FILE):
        print(f"ERROR: No {STATE_FILE} found.")
        return None

    with open(STATE_FILE, "r") as f:
        return json.load(f)
   
def save_command(command):

    with open(COMMAND_FILE, "w") as f:
        f.write(command)


def send_command_to_pi(command):

    url = f"http://{PI_IP}:{PI_PORT}/command"

    payload = {
        "command": command
    }

    try:
        requests.post(url, json=payload, timeout=2)
        print("Command sent to Raspberry Pi")
    except Exception as e:
        print("Failed to send command:", e)



def main():

    system_prompt = load_system_prompt()
    memory = load_memory()

    last_timestamp = None

    while True:
        state_json = read_state_file()

        if not state_json:
            time.sleep(STATE_POLL_INTERVAL)
            continue

        timestamp = state_json.get("uptime_seconds")

        # ignore already processed state
        if timestamp == last_timestamp:
            time.sleep(STATE_POLL_INTERVAL)
            continue

        last_timestamp = timestamp

        print("\nNEW STATE DETECTED")

        summary = summarize_state(state_json)

        print("\nENVIRONMENT SUMMARY:")
        print(summary)

        memory.append({
            "role": "user",
            "content": f"Robot environment summary:\n{summary}"
        })

        memory = trim_memory(memory)

        messages = [
            {"role": "system", "content": system_prompt}
        ] + memory

        reply = ollama_chat(MAIN_MODEL, messages)

        print("\nLLM COMMAND:")
        print(reply)

        commands = extract_commands(reply)

        for cmd in commands:
            save_command(cmd)
            #send_command_to_pi(cmd)
            print("Sent:", cmd)

        memory.append({
            "role": "assistant",
            "content": reply
        })

        save_memory(memory)

        time.sleep(STATE_POLL_INTERVAL)


if __name__ == "__main__":
    main()