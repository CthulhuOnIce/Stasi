import random

# Function to receive time in the form of "100d10h10m10s" and return the time in seconds
def time_to_seconds(time: str):
    seconds = 0
    if "d" in time:
        seconds += int(time.split("d")[0]) * 86400
        time = time.split("d")[1]
    if "h" in time:
        seconds += int(time.split("h")[0]) * 3600
        time = time.split("h")[1]
    if "m" in time:
        seconds += int(time.split("m")[0]) * 60
        time = time.split("m")[1]
    if "s" in time:
        seconds += int(time.split("s")[0])
    return seconds

# inverse of previous function, leaves out greatest unit if it is 0
def seconds_to_time(time: int):
    days = time // 86400
    time %= 86400
    hours = time // 3600
    time %= 3600
    minutes = time // 60
    time %= 60
    seconds = time

    if days > 0:
        return f"{days}d{hours}h{minutes}m{seconds}s"
    elif hours > 0:
        return f"{hours}h{minutes}m{seconds}s"
    elif minutes > 0:
        return f"{minutes}m{seconds}s"
    elif seconds > 0:
        return f"{seconds}s"
    else: # 0 seconds
        return "now"

def generate_random_id(): 
    nouns = open("wordlists/nouns.txt", "r").read().splitlines()
    adjectives = open("wordlists/adjectives.txt", "r").read().splitlines()
    return f"{random.choice(adjectives)}-{random.choice(adjectives)}-{random.choice(nouns)}"