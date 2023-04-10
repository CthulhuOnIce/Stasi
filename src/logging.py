import os
import datetime

def log(category_broad, category_fine, message, print_message=True, preserve_newlines=False):
    # create timestamp like JAN 6 2021 12:00:00
    os.makedirs("logs", exist_ok=True)
    timestamp = datetime.datetime.now().strftime("%b %d %Y %H:%M:%S")
    if not preserve_newlines:
        message = message.replace("\n", " ")
    # clean emojis, special characters
    print_msg = message.encode("latin-1", "replace").decode()
    if print_message: print(f"[{timestamp}] [{category_broad.upper()}] [{category_fine.upper()}] {print_msg}")
    with open(f"logs/{category_broad.lower()}.log", "a+") as f:
        f.write(f"[{timestamp}] [{category_fine.upper()}] {print_msg}\n")

def log_user(user):
    return f"{user} ({user.id})"

