import socket
import threading
import sys
import struct
import queue
import server

MAX_LEN_MSG = 4
SUCCESS = 0
FAILURE = 1

class Client:
    def __init__(self, HOST, PORT, name, queue_recv, lock_queue):
        self.connected = False
        self.HOST = HOST
        self.PORT = PORT
        self.name = name
        self.socket_server = None
        self.queue_recv = queue_recv
        self.lock_queue = lock_queue

    def init_client(self):
        try:
            self.socket_server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            print(f"Trying to connect to {self.HOST}:{self.PORT}")
            self.socket_server.connect((self.HOST, self.PORT))
            print("Connected.")
            name_bytes = self.name.encode(encoding="UTF-8")
            name_size_bytes = bytes([len(name_bytes)])
            self.socket_server.sendall(name_size_bytes)
            self.socket_server.sendall(name_bytes)

            recver_thread = threading.Thread(target=self.recver)
            recver_thread.daemon = True
            recver_thread.start()
            return SUCCESS
        except:
            return FAILURE

    #Sender method
    def sender_send(self, msgcode, msg=None):
        try:
            if (msgcode == server.MSGCODE_MESSAGE):
                msg_bytes = bytes( bytearray([msgcode]) + bytearray(msg.encode(encoding="UTF-8")) )
                msg_size = struct.pack("<I", len(msg_bytes))
                self.socket_server.sendall(msg_size)
                self.socket_server.sendall(msg_bytes)
                print(f"{self.name}: {msg}")
            else:
                print(f"Unexpected msgcode {msgcode}")
        except ConnectionResetError:
            self.disconnected()

    #receiver thread, listening to server socket
    def recver(self):
        print("Listening...")
        while True:
            try:
                #Receiving size
                size_bytes = self.socket_server.recv(MAX_LEN_MSG)
                if (len(size_bytes) == 0):
                    break
                size = int.from_bytes(size_bytes, byteorder="little")
                #Receiving actual message
                msg_bytes = bytearray(self.socket_server.recv(size))
                if (len(msg_bytes) == 0):
                    break
                print(f"Received {len(msg_bytes)} bytes from server")
                msgcode = msg_bytes.pop(0)
                print(f"Msgcode {msgcode}")
                to_queue = [msgcode] + msg_bytes.decode(encoding="UTF-8").split(":",2)
                print("Client: locking")
                self.lock_queue.acquire()
                print("Passing to queue")
                self.queue_recv.put(to_queue)
                self.lock_queue.release()
                print("Client: releasing lock")
            except ConnectionResetError:
                break
        self.disconnected()

    #parse msg_bytes
    def recver_parse(self, msg_bytes):
        msg = msg_bytes.decode(encoding="UTF-8").split(":",2)


    #If disconnected from server
    def disconnected(self):
        print("Disconnected from server")
        self.lock_queue.acquire()
        to_queue = [server.MSGCODE_SELFDISCONNECTED, None, None]
        self.queue_recv.put(to_queue)
        self.lock_queue.release()
