import threading
import tkinter as tk

import chatdb
import client
import server
import queue

ui_font = "Helvetica"
chat_fg = "#EAECEE"
chat_bg = "#17202A"
color_black = "#000000"
color_white = "#ffffff"


class GUI:
    def __init__(self):
        #vars
        self.secondary_window_alive = False
        self.client = None
        self.queue_recv = queue.Queue()
        self.lock_queue = threading.Lock()
        self.session_isactive = False
        self.recvr_thread = None
        self.colors = [("red","#ed1c24"), ("green","#22b14c"), ("blue","#3f48cc"), ("cyan","#00a2e8"), ("yellow","#ffc90e"),("magenta","#f00078")]
        self.list_connected = []

        #root
        self.root = tk.Tk()
        self.root.withdraw()
        self.root.protocol("WM_DELETE_WINDOW", self.destroy_root)
        try:
            self.root.tk.call("source", "libs\\Azure-ttk-theme-2.1.0\\azure.tcl")
            self.root.tk.call("set_theme", "dark")
        except tk.TclError:
            print("Error: failed to load external libraries. Themes will be disabled.")

        #main chat screen
        self.window_chat = tk.Tk()
        self.window_chat.withdraw()
        self.text_window_chat = tk.Text(self.window_chat, width=500, height=100, bg=chat_bg, fg=chat_fg, font=f"{ui_font} 12", padx=5, pady=5)
        self.scrollbar_window_chat = tk.Scrollbar(self.text_window_chat, command=self.text_window_chat.yview)
        self.entry_window_chat_send = tk.Entry(self.window_chat, width=500, font=f"{ui_font} 12")
        self.button_window_chat_send = tk.Button(self.window_chat, text="Send", font=f"{ui_font} 16", command=self.activate_button_send)
        self.listbox_window_chat_users = tk.Listbox(self.window_chat, font=f"{ui_font} 14", selectmode=tk.SINGLE)
        #Note: If I could implement Listbox, I'd have implemented it as a doubly-linked list.
        #With a dict(hash table) saving all connected clients' nodes in the listbox, insertion and deletion could be done in O(1)
        #Unfortunately tkinter does not allow access to nodes
        self.label_window_chat_participants = tk.Label(self.window_chat, text="Participants", font=f"{ui_font} 15")
        self.config_window_chat()


        #intro screen
        self.window_intro = tk.Toplevel()
        self.label_intro_welcome = tk.Label(self.window_intro, text="Welcome!\nConnect to a server or review history", justify=tk.CENTER, font=f"{ui_font} 16")
        self.button_intro_join = tk.Button(self.window_intro, text="Join a Server", font=f"{ui_font} 16", command=self.activate_window_intro_server)
        self.button_intro_db = tk.Button(self.window_intro, text="View Conversations", font=f"{ui_font} 16", command=self.activate_button_viewdb)
        self.label_intro_credits = tk.Label(self.window_intro, text="Chat Application, made by Alon Harell\n999alon@gmail.com", justify=tk.CENTER, font=f"{ui_font} 12")
        self.config_window_intro()


        #server connection window
        self.window_intro_server = tk.Toplevel()
        self.label_intro_server_ip = tk.Label(self.window_intro_server, text="Server IP:", font=f"{ui_font} 14")
        self.label_intro_server_port = tk.Label(self.window_intro_server, text="Server Port:", font=f"{ui_font} 14")
        self.label_intro_server_name = tk.Label(self.window_intro_server, text="Displayed Username:", font=f"{ui_font} 14")
        self.label_intro_server_status = tk.Label(self.window_intro_server, text = "", font=f"{ui_font} 12")
        self.entry_intro_server_ip = tk.Entry(self.window_intro_server, font=f"{ui_font} 14")
        self.entry_intro_server_port = tk.Entry(self.window_intro_server, font=f"{ui_font} 14")
        self.entry_intro_server_name = tk.Entry(self.window_intro_server, font=f"{ui_font} 14")
        self.button_intro_server_connect = tk.Button(self.window_intro_server, text="Connect", font=f"{ui_font} 16", command=self.activate_button_connect)
        self.config_window_intro_server()
        self.window_intro_server.withdraw()

        #View conversations window
        self.window_db = tk.Toplevel()
        self.listbox_db = tk.Listbox(self.window_db, font=f"{ui_font} 12", selectmode=tk.SINGLE)
        self.button_db_view = tk.Button(self.window_db, text="View conversation", font=f"{ui_font} 15", command=self.activate_button_viewchat)
        self.label_window_db = tk.Label(self.window_db, text="Pick a coversation to view:", font=f"{ui_font} 15")
        self.scrollbar_db = tk.Scrollbar(self.window_db)
        self.config_window_db()
        self.window_db.withdraw()


        #Run
        self.root.mainloop()


    #Receive incoming message from queue and display them
    def recv_from_queue(self):
        self.lock_queue.acquire()
        if (self.queue_recv.empty() == False):
            print("recv_from_queue awakened")
            from_queue = self.queue_recv.get()
            self.lock_queue.release()
            print("releasing lock")
            msgcode = from_queue[0]
            src_addr = from_queue[1]
            src_name = from_queue[2]

            if (msgcode == server.MSGCODE_MESSAGE):
                message = from_queue[3]
                print(f"From {src_name}: {message}")
                self.display_window_chat(msgcode, src_name, message)

            if ((msgcode == server.MSGCODE_JOINED_NEW) or (msgcode == server.MSGCODE_INSIDE)):
                self.list_connected.append(src_addr)
                self.listbox_window_chat_users.insert(tk.END,src_name)
                self.listbox_window_chat_users.itemconfig(tk.END, foreground=self.getcolor(src_name, getval=True))
                if (msgcode == server.MSGCODE_JOINED_NEW):
                    self.display_window_chat(msgcode, src_name)

            if (msgcode == server.MSGCODE_LEFT):
                index = self.list_connected.index(src_addr)
                self.list_connected.remove(src_addr)
                self.listbox_window_chat_users.delete(index)
                self.display_window_chat(msgcode, src_name)

            if (msgcode == server.MSGCODE_SELFDISCONNECTED):
                self.display_window_chat(msgcode, None)
                self.button_window_chat_send.config(state=tk.DISABLED)

            self.window_chat.after(100, self.recv_from_queue)
        else:
            self.window_chat.after(100, self.recv_from_queue)
            self.lock_queue.release()

    #Method to display messages in chat
    def display_window_chat(self, msgcode, src_name, message=None):
        self.text_window_chat.config(state=tk.NORMAL)
        if (msgcode == server.MSGCODE_MESSAGE):
            self.text_window_chat.insert(tk.END, f"{src_name}\n", self.getcolor(src_name))
            self.text_window_chat.insert(tk.END, f"{message}\n\n", "text")
        if (msgcode == server.MSGCODE_JOINED_NEW):
            self.text_window_chat.insert(tk.END, f"{src_name} joined!\n", "alert")
            self.text_window_chat.insert(tk.END, f"\n", "text")
        if (msgcode == server.MSGCODE_LEFT):
            self.text_window_chat.insert(tk.END, f"{src_name} left!\n", "alert")
            self.text_window_chat.insert(tk.END, f"\n", "text")

        if (msgcode == server.MSGCODE_SELFDISCONNECTED):
            self.text_window_chat.insert(tk.END, f"Disconnected from server\n", "alert")
            self.text_window_chat.insert(tk.END, f"\n", "text")

        self.text_window_chat.config(state=tk.DISABLED)
        self.text_window_chat.see(tk.END)


    ############# Destruction methods, for closing windows ##################

    def destroy_root(self):
        self.root.destroy()
        self.root.quit()
        #if (self.recvr_thread != None):
        exit(0)

    def destroy_window_chat(self):
        self.window_chat.destroy()
        self.destroy_root()

    def destroy_window_intro(self):
        if (self.session_isactive == False):
            self.destroy_root()
        else:
            self.window_intro.destroy()

    def destroy_window_intro_server(self):
        self.window_intro_server.withdraw()
        self.secondary_window_alive = False

    def destroy_window_db(self):
        self.window_db.withdraw()
        self.secondary_window_alive = False


    ############# Config methods, for setup of windows ##################

    def config_window_chat(self):
        #window
        self.window_chat.title("Chat Application")
        self.window_chat.protocol("WM_DELETE_WINDOW", self.destroy_window_chat)
        self.window_chat.configure(width=1000, height=900)
        #text
        self.text_window_chat.place(relheight=0.8, relwidth=0.8, rely=0)
        self.text_window_chat.config(state=tk.DISABLED, yscrollcommand=self.scrollbar_window_chat.set)
        #scrollbar
        self.scrollbar_window_chat.place(relheight=1, relx=0.974)
        self.scrollbar_window_chat.config(command=self.text_window_chat.yview)
        #entry
        self.entry_window_chat_send.place(relwidth=0.7, height=100,relx=0.01, rely=0.82)
        self.entry_window_chat_send.bind("<Return>", self.activate_button_send)
        #buttons
        self.button_window_chat_send.place(relwidth=0.095, relheight=0.105, relx=0.72, rely=0.82)
        self.button_window_chat_send.config(state=tk.DISABLED)
        #label
        self.label_window_chat_participants.place(relx=0.83, rely=0.005)
        #listbox
        self.listbox_window_chat_users.place(relwidth = 0.185, height = 600, relx = 0.81, rely=0.05)
        #theme
        try:
            self.window_chat.tk.call("source", "libs\\Azure-ttk-theme-2.1.0\\azure.tcl")
            self.window_chat.tk.call("set_theme", "dark")
        except tk.TclError:
            print("Error: failed to load external libraries. Themes will be disabled.")
        self.create_tags()


    def config_window_intro(self):
        #window
        self.window_intro.title("Chat Application")
        self.window_intro.protocol("WM_DELETE_WINDOW", self.destroy_window_intro)
        self.window_intro.configure(width=500, height=500)
        self.window_intro.resizable(width=False, height=False)
        #labels
        self.label_intro_welcome.place(relx=0.15, rely=0.20)
        self.label_intro_credits.place(relx=0.20, rely=0.80)
        #buttons
        self.button_intro_join.place(relx=0.35, rely=0.40)
        self.button_intro_db.place(relx=0.30, rely=0.60)


    def config_window_intro_server(self):
        #window
        self.window_intro_server.title("Chat Application: Connect")
        self.window_intro_server.protocol("WM_DELETE_WINDOW",self.destroy_window_intro_server)
        self.window_intro_server.configure(width=500, height=300)
        self.window_intro_server.resizable(width=False, height=False)
        #Labels
        self.label_intro_server_ip.place(relx = 0.07, rely = 0.15)
        self.label_intro_server_port.place(relx = 0.07, rely = 0.3)
        self.label_intro_server_name.place(relx=0.07, rely=0.45)
        #Entries
        self.entry_intro_server_ip.place(relx = 0.5, rely = 0.15)
        self.entry_intro_server_port.place(relx=0.5, rely=0.3)
        self.entry_intro_server_name.place(relx=0.5, rely=0.45)
        #Buttons
        self.button_intro_server_connect.place(relx=0.1, rely=0.7)


    def config_window_db(self):
        #window
        self.window_db.config(width=500, height=800)
        self.window_db.title("Chat Application: View conversations")
        self.window_db.protocol("WM_DELETE_WINDOW", self.destroy_window_db)
        #listbox
        self.listbox_db.place(relwidth=0.8, relheight=0.8, relx=0.1, rely=0.1)
        self.listbox_db.config(yscrollcommand=self.scrollbar_db.set)
        #labels
        self.label_window_db.place(relx=0.2, rely=0.05)
        #Buttons
        self.button_db_view.place(relx=0.3, rely=0.92)
        #Scrollbar
        self.scrollbar_db.place(rely=0.1, relx=0.9)
        self.scrollbar_db.config(command=self.listbox_db.yview)


    ############# Activation methods, for pressed buttons ##################

    def activate_window_intro_server(self):
        if (self.secondary_window_alive == False):
            print("opening connection window")
            self.label_intro_server_status.config(text="")
            self.secondary_window_alive = True
            self.window_intro_server.deiconify()


    def activate_button_connect(self):
        self.label_intro_server_status.config(text="Connecting...")
        self.label_intro_server_status.place(relx=0.5, rely=0.7)  # display "Connecting..."
        HOST = self.entry_intro_server_ip.get()
        PORT = int(self.entry_intro_server_port.get())
        name = self.entry_intro_server_name.get()
        self.client = client.Client(HOST, PORT, name, self.queue_recv, self.lock_queue)
        if (self.client.init_client() == client.FAILURE):
            self.label_intro_server_status.config(text="ERROR! Could not connect.")
        else:
            self.label_intro_server_status.config(text="Connected!")
            self.session_isactive = True
            self.destroy_window_intro_server()
            self.destroy_window_intro()
            self.window_chat.title(f"Chat Application  - Connected to ({HOST},{PORT})")
            self.button_window_chat_send.config(state=tk.NORMAL)
            self.window_chat.deiconify()
            self.list_connected.append(f"({HOST},{PORT})")
            self.listbox_window_chat_users.insert(0,name)
            self.listbox_window_chat_users.itemconfig(0, foreground=self.getcolor(name,getval=True))
            self.recv_from_queue()


    def activate_button_send(self, args=None):
        message = self.entry_window_chat_send.get()
        if (len(message) > 0):
            self.entry_window_chat_send.delete(0,tk.END)
            self.client.sender_send(server.MSGCODE_MESSAGE, message)
            self.display_window_chat(server.MSGCODE_MESSAGE, self.client.name, message)


    def activate_button_viewdb(self):
        if (self.secondary_window_alive == False):
            print("opening db window")
            self.secondary_window_alive = True
            print("Getting conversations...")
            chats_list = chatdb.get_all_chats()
            self.update_listbox_db(chats_list)
            self.window_db.deiconify()


    def activate_button_viewchat(self):
        chat_selected = self.listbox_db.get(tk.ANCHOR)
        messages = chatdb.get_all_messages(chat_selected)
        for message in messages:
            self.display_window_chat(message[0],message[1],message[2])

        self.session_isactive = True
        self.destroy_window_intro()
        self.destroy_window_db()

        self.window_chat.deiconify()


    ############# Helper methods ##################

    def update_listbox_db(self, lst):
        for i in range(0,len(lst)):
            self.listbox_db.insert(i,lst[i])

    def create_tags(self):
        self.text_window_chat.tag_config("alert", background=color_black, foreground=color_white, font=f"{ui_font} 13 bold italic")
        self.text_window_chat.tag_config("text", background=chat_bg, foreground=chat_fg, font=f"{ui_font} 12")
        for color in self.colors:
            self.text_window_chat.tag_config(color[0], background=chat_bg, foreground=color[1], font=f"{ui_font} 13 bold")

    def getcolor(self, txt, getval=False):
        i = 0
        if (getval):
            i = 1

        val = sum(ord(ch) for ch in txt)
        return self.colors[val%len(self.colors)][i]





if __name__ == "__main__":
    gui = GUI()
