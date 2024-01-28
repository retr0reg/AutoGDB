from autogdb import *
import json
import os

from rich import print
from rich.progress import Progress
import argparse
import warnings

warnings.filterwarnings("ignore", message="You are trying to use a chat model.*")
CACHE_FILE_PATH = '.server_cache.autogdb.json'
lo = Logger()

def parsing():

    parser = argparse.ArgumentParser(
        prog='AutoGDB',
        description='Enable GPT in your reversing job with GDB.',
    )
    parser.add_argument('--serverless',help='Run AutoGDB without bulit-in server',dest='serverless', action='store_true')
    parser.add_argument('--clue',help='Possible provided clues or helpful description of this challenge?', dest='clue')
    parser.add_argument('--clean-history',help='Clear previous commandline history of AutoGDB.', action='store_true')
    return parser.parse_args()


def clear_screen():
    import platform
    if platform.system() == "Windows":
        subprocess.run("cls", shell=True)
    else:
        subprocess.run("clear", shell=True)


def banner():
    banner = """\
    \n\n
           _____                _____)  ______    ______   
          (, /  |             /        (, /    ) (, /    ) 
            /---|     _/_ ___/   ___     /    /    /---(   
         ) /    |_(_(_(__(_)/     / )  _/___ /_ ) / ____)  
        (_/                (____ /   (_/___ /  (_/ ("""
    
    author = """\n\
        Enable GPT in your reversing job.
        [bold red]>[/bold red] Author [bold blue]Retr0Reg[/bold blue], ChatWithBinary Team.       
    """
    clear_screen()
    print(banner,end='')
    print(author,end='')
    print('\n')
    return banner+author+'\n'

def check_for_keys():
    OPENAI_API_BASE = os.getenv("OPENAI_API_BASE", default="https://api.openai.com/v1")
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
    lo.success("Loaded API key and base URL from environment.")

    try:
        from api_key import OPENAI_API_KEY, OPENAI_API_BASE
    except:
        if not OPENAI_API_KEY or not OPENAI_API_BASE:
            lo.fail("API key or base URL not found.")
            OPENAI_API_KEY = input("Please enter your OpenAI API key: ").strip()
            OPENAI_API_BASE = input("Please enter the OpenAI API base URL: ").strip()

            with open('api_key.py', 'w') as file:
                file.write(f'OPENAI_API_KEY = "{OPENAI_API_KEY}"\n')
                file.write(f'OPENAI_API_BASE = "{OPENAI_API_BASE}"\n')

            lo.success("api_key.py file created with your API key and base URL.")

            # Re-import after creating the file
            from api_key import OPENAI_API_KEY, OPENAI_API_BASE

    return OPENAI_API_KEY, OPENAI_API_BASE

def console_input(input_str: str) -> str:
    print(input_str, end='')
    input_text = input(' >>> \033[0m')
    return input_text

def get_server_info():
    if os.path.exists(CACHE_FILE_PATH):
        with open(CACHE_FILE_PATH, 'r') as cache_file:
            try:
                server_info = json.load(cache_file)
                addr = server_info['ip']
                port = server_info['port']
                
                if (not addr) or (not port):
                    raise KeyError(f"Server address and port saved is empty, please save it again by deleting:{CACHE_FILE_PATH}")
                
                return addr,port
                
            except json.JSONDecodeError:
                lo.fail("Cache file is corrupted. Please enter server details again.")

    # Cache file doesn't exist or is corrupted, ask the user for info
    server_ip = console_input("    [bold light_steel_blue1][?] Please enter your server IP:[/bold light_steel_blue1] ").strip()
    server_port = console_input("    [bold light_steel_blue1][?] Please enter your server port:[/bold light_steel_blue1] ").strip()
    try:
        with open(CACHE_FILE_PATH, 'w') as cache_file:
            json.dump({'ip': server_ip, 'port': server_port}, cache_file)
        lo.success(f"Server address and port saved, change it by deleting {CACHE_FILE_PATH}.")
    except Exception as e:
        lo.fail("Save address and port failed, please check for your privilege and etc.")

    return server_ip, server_port

import subprocess
import socket
import signal
import os

class AutoGDBServer:
    def __init__(self,url,port) -> None:
        self.url = url
        self.port = port
        self.proc = None

    
    def check_port(self) -> bool:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(1)
            try:
                s.connect((self.url, int(self.port)))
                return False
            except socket.error:
                return True

    def start_uvicorn(self):
        try:
            if not self.check_port():
                raise Exception(f"The port {self.port} for autogdb server is used/busy, please change your port")
            lo.success(f"AutoGDB server started at {self.url}:{self.port}")
            lo.info(f"You can use: ",end='')
            print(f"[bold green]autogdb {self.url} {self.port}[/bold green]")
            self.proc = subprocess.Popen(["uvicorn", "main:app", "--host", str(self.url), "--port", str(self.port), "--reload"],
                                        stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,
                                        cwd="server/"
                                    )

        except Exception as e:
            lo.fail(str(e))
    
    def exit(self):
        os.killpg(os.getpgid(self.proc.pid), signal.SIGTERM)

import time
from rich.progress import Progress, SpinnerColumn, TextColumn
def await_until_connection(autogdb: AutoGDB):
    lo.info("Waiting AutoGDB to connect....")
    with Progress("   ",SpinnerColumn(), "[progress.description]{task.description}",transient=True) as progress:
        task = progress.add_task("[bold medium_purple2]Waiting for connecting...[/bold medium_purple2]", total=None)
        while True:
            try:
                frame = autogdb.await_autogdb_connecton()
                if frame['message'] == 'success':
                    time.sleep(0.1)
                    lo.success(f"Recieved connection from:",PrevReturn=True)
                    print(f"[bold medium_purple1]    Binary Name: {frame['name']}\n    Binary Path: {frame['path']}[/bold medium_purple1]")
                    return frame['name'],frame['path']
                elif frame['message'] == 'awaiting':
                    pass
                elif frame['message'] == 'error':
                    lo.fail(f"Error recieved from AutoGDB connection: {frame['detail']}")
                else:
                    lo.fail(f"Unknown respone from AutoGDB connection: {frame}")
            except Exception as e:
                pass
            time.sleep(5)
            progress.update(task, advance=0.1)

args = None
def setup():
    global args
    USER_OPENAI_API_KEY, USER_OPENAI_API_BASE = check_for_keys()
    ip, port = get_server_info()
    args = parsing()
    history_manager = CliHistory()
    autogdb = AutoGDB(server=ip, port=port)
    autogdb_server = AutoGDBServer(ip,port)

    if args.clean_history:
        history_manager.clear_history()
        lo.info("History cleaned!\n")
        exit()

    if args.serverless:
        name=''
        path=''
    else:
        autogdb_server.start_uvicorn()
        name,path = await_until_connection(autogdb=autogdb)

    if args.clue:
        pwnagent = PwnAgent(USER_OPENAI_API_KEY, USER_OPENAI_API_BASE, autogdb.tool(),binary_name=name,binary_path=path,clue=args.clue)
    else:
        pwnagent = PwnAgent(USER_OPENAI_API_KEY, USER_OPENAI_API_BASE, autogdb.tool(),binary_name=name,binary_path=path)

    chatagent = ChatAgent(USER_OPENAI_API_KEY, USER_OPENAI_API_BASE, pwnagent)

    return chatagent, autogdb_server, history_manager


def cli():
    chatagent, autogdb_server, history_manager = setup()

    history_manager.load_history()
    try:
        while True:
            text_query = console_input(f"\n  [bold light_steel_blue1] Talk to [/bold light_steel_blue1][bold plum2]GDBAgent[/bold plum2]")
            print(f"  [bold medium_purple1]:snowboarder: GDBAgent[/bold medium_purple1]: ", end='')
            chatagent.chat_and_assign(text_query)
            history_manager.save_history()
    
    except KeyboardInterrupt:
        lo.info("Bye!",PrevReturn=True)
        history_manager.save_history()

    except Exception as e:
        lo.fail(e)

    finally:
        if not args.serverless:
            autogdb_server.exit()

if __name__ == "__main__":
    banner()
    cli()