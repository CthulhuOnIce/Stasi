import yaml

C = {}
G = {}  # global variables across all cogs and namespaces

def load_config():
    global C
    try:
        with open("config.yml", "r") as r:
            C = yaml.load(r.read(), Loader=yaml.FullLoader)
    except FileNotFoundError:
        print("No config.yml, please copy and rename config-example.yml and fill in the appropriate values.")
        exit()

def initialize_globals():
    return

def get_global(key):
    if key in G:
        return G[key]

def set_global(key, value):
    G[key] = value

load_config()
initialize_globals()