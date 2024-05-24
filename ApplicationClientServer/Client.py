import socket
import random
import time
import threading
import struct
from socket import *
import msvcrt
from Configuration import *


class Client:

    #----------------------------------------- Client Constructor  ---------------------------------------------------
    def __init__(self):
        # Choose random name from the list of names
        self.random_first_name = random.choice(first_names)


    #----------------------------------------- Client Receive Message  ---------------------------------------------------

    """ Function that receive the message on broadcast from the server """
    def receivedMessage(self):
        sock = socket(AF_INET, SOCK_DGRAM)
        sock.setsockopt(SOL_SOCKET, SO_REUSEADDR, 1)
        sock.bind(("", broadcast_destination_port))
        message = None
        while message is None:
            try:
                sock.settimeout(0.01)
                message = sock.recvfrom(buffer_size)
            except:
                continue
        return message


    #----------------------------------------- Client Game Mode ---------------------------------------------------

    """ Function that handle the side of the client of the game - waiting fo an answer from the player, and handle it if another player correct first or 10 sec passed """
    def startPlaying(self, tcp_socket):
        while True:
            try:
                # Thread that check for a message from the server if another player answer correct first
                someone_answer_correct = threading.Thread(daemon=True, target=self.is_correct_answer_list_not_empty, args=(tcp_socket,))
                someone_answer_correct.start()
                # Initialized 10 sec to answer
                while True:
                    # Check if a key has been pressed or if the timeout has been reached
                    if msvcrt.kbhit():
                        # If the reason if from an input from the player
                        val = msvcrt.getch()
                        print(val.decode("utf-8"))
                        # If not valid key 
                        if val not in valid_answers:
                            print("\033[91mInvalid input. Please enter a valid key - ['T', 'F', 'Y', 'N', '0', '1']\033[0m")
                            continue
                        # If valid key
                        else:
                            tcp_socket.sendall(val)
                            break
                    # If the thread of checking if someone correct first stop waiting for answer from the player because someone answer first
                    elif not someone_answer_correct.is_alive():
                        val = b""  # If no key pressed, send empty string
                        tcp_socket.sendall(val)
                        break
                    time.sleep(0.1) # To reduce CPU usage

                # Receive response from the server and print it
                msgFromServer = tcp_socket.recv(buffer_size).decode("utf-8")
                if ("Game over" in msgFromServer):
                    print("\033[93m" + msgFromServer + "\033[0m")
                    break
                print("\033[94m" + msgFromServer + "\033[0m")
                time.sleep(0.1) # To reduce CPU usage
            except ConnectionResetError:
                print("\033[91m" + f"Server {server_name} disconnected unexpectedly." + "\033[0m")
                return
            except Exception as e:
                pass


    """ Function that check for a message from the server if another player answer correct first """
    def is_correct_answer_list_not_empty(self, tcp_socket):
        try:
            response = tcp_socket.recv(buffer_size).decode("utf-8")
            return 
        except ConnectionResetError:
            return False
        except Exception as e:
            return False


    #----------------------------------------- Client TCP connection  ---------------------------------------------------

    """ Client connect to the server by a TCP socket """
    def connectTCP(self, address, port_num):
        TCP_IP, _ = address
        try:
            tcp_socket = socket(AF_INET, SOCK_STREAM)
            tcp_socket.connect((TCP_IP, port_num))
        
            # Sending his name to the server after connect success
            tcp_socket.send(bytes(self.random_first_name + "\n", "utf-8"))
            data = tcp_socket.recv(buffer_size).decode("utf-8")
        
        except ConnectionResetError:
            print("\033[91m" + f"Server {server_name} disconnected unexpectedly." + "\033[0m")
            return 
        
        except Exception as e:
            print("\033[91m" + f"Error connecting to server: {e}" + "\033[0m")
            return  
        # If the game over while trying to connect because players left the game for example
        if "Game over" in data:
            print("\033[93m" + data + "\033[0m")
            return
        print("\033[95m" + data + "\033[0m")
        # After connecting to the server' start playing
        self.startPlaying(tcp_socket)


    #----------------------------------------- Check Corrupted Data  ---------------------------------------------------

    """ Function that check if the message that arrived from the server in the right format and not corrupted """
    def getUnPackMessage_CheckIfCorrupted(self, receivedData):
        # check if message is correct type - if yes return port number else return None
        try:
            unPackMsg = struct.unpack("!Ib32sH", receivedData)
        # unPackMsg[0] != 2882395322 - This check ensures that the first field of the unpacked data matches a specific magic cookie value.
        # This value (2882395322), when converted to hexadecimal (0xABCDDCBA), is often used as a magic number to identify certain types of packets or messages.
        # unPackMsg[1] != 2 - This check ensures that the second field of the unpacked data matches a specific message type value.
        # In this case, the value 2 may indicate that the received data is an offer packet.
        # unPackMsg[2] < 1024 or unPackMsg[2] > 65535 - This check ensures that the third field of the unpacked data, which represents the port number, falls within a valid range of port numbers.
            if unPackMsg[0] != 2882395322 or unPackMsg[1] != 2 or unPackMsg[3] < 1024 or unPackMsg[3] > 65535:
                print("\033[91m" + "Corrupted Message! try to receive the message from the server again"+ "\033[0m")
                return None
        except:  # message format not good
            print("\033[91m" + "Corrupted Message! try to receive the message from the server again"+ "\033[0m")
            return None
        return unPackMsg


    #----------------------------------------- Start The Client ---------------------------------------------------

    """ Function that start handle everything - listen to the server, handle message of connection, connect to TCP and repeat it after game over """
    def startClient(self):
        while True:
            print("\033[1;92mClient started, listening for offer requests...\033[0m")
            receivedData, address = self.receivedMessage()
            unPackMsg = self.getUnPackMessage_CheckIfCorrupted(receivedData)
            if unPackMsg is None:
                continue
            server_name = unPackMsg[2].decode("utf-8").strip()
            print(f"\033[1;92mReceived offer from server {server_name} at address {address[0]}, attempting to connect...\033[0m")
            try:
                portNum = unPackMsg[3]
                self.connectTCP(address, portNum)
            except:
                continue
            print("\033[1;92mServer disconnected, listening for offer requests...\033[0m")
            time.sleep(0.1) # To reduce CPU usage


# run client
if __name__ == '__main__':
    client = Client()
    client.startClient()