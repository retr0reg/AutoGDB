import gdb
import requests
import time

import gdb
import os
import signal

session_without_proxies = requests.Session()
session_without_proxies.trust_env = False
# This is without proxy; only for testing

import base64

def encode_response(text):
    text_bytes = text.encode('utf-8')
    base64_bytes = base64.b64encode(text_bytes)
    return base64_bytes.decode('utf-8')

class Logger:
    def __init__(self) -> None:
        self.SUCCESS_PREFIX = "\033[92m[*]\033[0m"
        self.SUCCESS_TEXT_COLOR = "\033[94m"

        self.INFO_PREFIX = "\033[33m[info]\033[0m"
        self.INFO_TEXT_COLOR = "\033[93m"

        self.FAILURE_PREFIX = "\033[90m[!]\033[0m"
        self.FAILURE_TEXT_COLOR = "\033[91m"

        self.RESET_COLOR = "\033[0m"

    def info(self,message):
        print(f"{self.INFO_PREFIX} {self.INFO_TEXT_COLOR}{message}{self.RESET_COLOR}")
        

    def success(self,message,PrevReturn=False):
        if not PrevReturn:
            print(f"{self.SUCCESS_PREFIX} {self.SUCCESS_TEXT_COLOR}{message}{self.RESET_COLOR}")
        else:
            print(f"\n\n{self.SUCCESS_PREFIX} {self.SUCCESS_TEXT_COLOR}{message}{self.RESET_COLOR}")

    def fail(self,message):
        print(f"{self.FAILURE_PREFIX} {self.FAILURE_TEXT_COLOR}{message}{self.RESET_COLOR}")

lo = Logger()

def send_response(response, command, SERVER,success=False):
    try:
        # Adjust the field names if necessary to match the expected schema
        json_payload = {"response": encode_response(response), "instruction": command}
        rs = session_without_proxies.post(f"{SERVER}/see-callback/", json=json_payload)
        # Now use without proxies
        if rs.status_code == 200:
            lo.success("Response sent successfully.",PrevReturn=True)
        else:
            lo.fail(f'Send_response failed, check for server connection please: {rs.status_code}')
    except Exception as e:
        lo.fail(f'Exception occurred while sending response: {e}')

class GdbGptCommand(gdb.Command):
    "Fetch and execute commands from a remote server"

    def __init__(self):
        super(GdbGptCommand, self).__init__("autogdb", gdb.COMMAND_USER)
        self.server = None
        self.port = None
        self.binary_name = None

    def test_connection(self):
        server_url = f"http://{self.server}:{self.port}"
        try:
            response = session_without_proxies.get(f"{server_url}/test-connection-gdb/?binary_name={self.binary_name}", timeout=3)
            if response.status_code == 200:
                lo.success(f"Connected to {server_url}!!!")
            else:
                lo.fail(f"Connection to {server_url} failed. Status Code: {response.status_code}")
        except requests.exceptions.RequestException as e:
            lo.fail(f"Connection to {server_url} failed. Error: {e}")
    

    def invoke(self, arg, from_tty):
        if arg:
            args = arg.split()
            if len(args) == 2:
                self.server, self.port = args
                self.test_connection()
            else:
                lo.info("Usage: autogdb <server> <port>")
                return
        else:
            lo.info("Usage: autogdb <server> <port>\nNo server and port provided.")
            return

        server_url = f"http://{self.server}:{self.port}"
        while True:
            try:
                response = session_without_proxies.get(f"{server_url}/get-instruction", timeout=30)
                time.sleep(2)
                if response.status_code == 200:
                    data = response.json()
                    instruction = str(data.get('instruction'))
                    if instruction:
                        lo.success(f"Executing instruction from server: {instruction}")
                        if instruction == "run" or instruction =='r':
                            lo.info("ChatGPT is running \'run\' command, please manuly use Ctrl+C")

                        try:
                            # Attempt to execute the instruction and capture the output.
                            responses = gdb.execute(instruction, to_string=True)
                            print(responses)
                            if instruction == "run" or instruction =='r':
                                lo.info("please input the extra result of the command \'run\' (The part before ^C): ")
                                responses += input()
                                responses = str(responses)
                                print('\r\n\n')
                            send_response(response=responses, command=instruction, SERVER=server_url)
                        except gdb.error as e:
                            error_message = str(e)
                            error_message = f"An error occurred: {error_message}"
                            error_message = str(error_message)
                            lo.fail(error_message)
                            send_response(response=error_message, command=instruction, SERVER=server_url,success=False)

                else:
                    if response.status_code == 404:
                        pass
                    else:
                        lo.fail(f"Failed to connect to server. Status Code: {response.status_code}")

            except Exception as e:
                lo.fail(f"An error occurred: {e}")
                time.sleep(2)

GdbGptCommand()