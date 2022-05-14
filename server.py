import queue
import socket
import threading
import sys
import struct
import chatdb


MSGCODE_MESSAGE = 0x1
MSGCODE_JOINED_NEW = 0x2
MSGCODE_LEFT = 0x3
MSGCODE_INSIDE = 0x4
MSGCODE_SELFDISCONNECTED = 0x5
IGNORE_LST = [MSGCODE_INSIDE]

MAX_LEN_MSG = 4
MAX_LEN_NAME = 1

class Server:
    def __init__(self, HOST, PORT):
        self.connected_clients = dict()
        self.queue_msgs = queue.Queue() #used for messages from server
        self.lock_queue = threading.Lock()
        self.lock_clients = threading.Lock()
        self.HOST = HOST
        self.PORT = PORT
        self.cv_queue_notempty = threading.Condition(lock=self.lock_queue)
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server_socket:
            print("Binding socket")
            server_socket.bind((self.HOST, self.PORT))
            print("Initializing db")
            self.db_name = chatdb.new_chat(server_socket.getsockname())
            if (self.db_name != None):
                print(f"DB initialized, Server name in DB:\n{self.db_name}")
            self.db_msg_count = 0
            print("Starting sender thread")
            self.sender_thread = threading.Thread(target=self.sender_queuelisten)
            self.sender_thread.start()
            server_socket.listen()
            print(f"Listening on socket {self.HOST}:{self.PORT}")
            while True: #Listening and accepting new clients
                client_connection, client_addr = server_socket.accept()
                self.lock_clients.acquire()
                self.connected_clients[client_connection] = [client_addr, "No_Name"]
                self.lock_clients.release()
                client_thread_recv = threading.Thread(target=self.recv_client, args=[client_connection, client_addr]) #thread to listen to each client
                client_thread_recv.start()


    #Rceiving from client
    def recv_client(self, client_connection, client_addr):
        #Receiving client's username
        print(f"New client connected, {client_addr}")
        namesize_bytes = client_connection.recv(MAX_LEN_NAME)
        namesize = int.from_bytes(namesize_bytes,byteorder="little")
        name_bytes = client_connection.recv(namesize)
        if (len(namesize_bytes) == 0) or (len(namesize_bytes) == 0):
            self.closed_connection(client_connection)
            return None
        client_name = name_bytes.decode(encoding = "UTF-8")
        self.connected_clients[client_connection][1] = client_name

        self.queue_msgs_put(client_connection, MSGCODE_JOINED_NEW, client_addr, client_name)
        for other_client in self.connected_clients.keys():
            if (other_client != client_connection):
                other_addr , other_name = self.connected_clients[other_client]
                self.queue_msgs_put(client_connection, MSGCODE_INSIDE, other_addr, other_name)

        while True:
            try:
                size_bytes = client_connection.recv(MAX_LEN_MSG)
                if (len(size_bytes) == 0):
                    break
                size = int.from_bytes(size_bytes,byteorder="little")
                msg_bytes = bytearray(client_connection.recv(size))
                if (len(msg_bytes) == 0):
                    break
                print(f"Recieved {len(msg_bytes)} bytes")
                msgcode = msg_bytes.pop(0)
                if (msgcode == MSGCODE_MESSAGE):
                    msg = msg_bytes.decode(encoding = "UTF-8")
                    print(f"{client_name} {client_addr}: {msg}")
                    self.queue_msgs_put(client_connection, MSGCODE_MESSAGE, client_addr, client_name, msg)
                else:
                    print(f"ERROR: RECEIVED UNEXPECTED CODE from {client_addr}")
            except ConnectionResetError:
                break

        self.closed_connection(client_connection)


    #Connection died/closed
    def closed_connection(self, client_connection):
        self.lock_clients.acquire()
        client_addr, client_name = self.connected_clients.pop(client_connection)
        self.lock_clients.release()
        print(f"Client {client_name} {client_addr} closed their connection.")
        self.queue_msgs_put(client_connection, MSGCODE_LEFT, client_addr, client_name)


    #All sending through this method! Wrapper.
    def queue_msgs_put(self, client_connection, msgcode, src_addr, src_name, msg=None):
        msg_bytes = self.sender_format(msgcode, src_addr=src_addr, src_name=src_name, msg=msg)
        self.lock_queue.acquire()
        self.queue_msgs.put([msg_bytes, client_connection, msgcode])
        if (self.queue_msgs.empty() == False):
            print("Waking up sender...")
            self.cv_queue_notempty.notify()
        self.lock_queue.release()

    #Formatting sent message, to correct msg_bytes format. Also logs in DB.
    def sender_format(self, msgcode, src_addr=None, src_name=None, msg=None):
        if (msgcode == MSGCODE_MESSAGE):
            msg_str = f"{src_addr}:{src_name}:{msg}"
            msg_bytes = bytes( bytearray([MSGCODE_MESSAGE]) + bytearray(msg_str.encode(encoding="UTF-8")) )
        else:
            msg_str = f"{src_addr}:{src_name}"
            msg_bytes = bytes(bytearray([msgcode]) + bytearray(msg_str.encode(encoding="UTF-8")))
        chatdb.add_message(self.db_name, msgcode, src_addr, src_name, self.db_msg_count, IGNORE_LST, msg=msg) #logging in DB
        self.db_msg_count += 1
        return msg_bytes

    #Server thread waiting for sending queue to fill. If empty, sleeps (to save CPU). Wakes on CV.
    def sender_queuelisten(self):
        while True:
            self.lock_queue.acquire()
            if(self.queue_msgs.empty() == False):
                print("queue not empty, waking")
                msg_bytes, client_connection, msgcode = self.queue_msgs.get()
                self.lock_queue.release()
                if (msgcode == MSGCODE_INSIDE):
                    self.send_allclients(msg_bytes, target=client_connection)
                else:
                    self.send_allclients(msg_bytes, clientsrc=client_connection)
            else:
                print("queue empty, going to sleep")
                self.cv_queue_notempty.wait()
                self.lock_queue.release()


    def send_allclients(self, msg_bytes, clientsrc=None, target=None):
        msg_size = struct.pack("<I", len(msg_bytes))
        if (target != None):
            self.send_toclient(target, msg_bytes, msg_size)
        else:
            self.lock_clients.acquire()
            clients = [client for client in self.connected_clients.keys()]
            self.lock_clients.release()
            for client in clients:
                if (client != clientsrc):
                    self.send_toclient(client, msg_bytes, msg_size)

    def send_toclient(self, client, msg_bytes, msg_size):
        try:
            client.sendall(msg_size)
            client.sendall(msg_bytes)
            print(f"sent to client {client}")
        except:
            print(f"Error sending to client {client}")


if __name__ == "__main__":
    if (len(sys.argv) < 2) or (int(sys.argv[1]) > 65535 or  int(sys.argv[1]) < 1):
        print("ERROR: Invalid arguments")
        exit(1)

    PORT = int(sys.argv[1])
    HOST = ""
    if (len(sys.argv) > 2):
        HOST = sys.argv[2]

    server = Server(HOST, PORT)


