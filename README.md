# ChatApplication
A chat application, runs a server or a client for public chat rooms. Can save conversations in firebase db.


## RUNNING
To launch the server, run:
On windows:
python server.py <port> <optional: IPv4 address>
On linux:
python3 server.py <port> <optional: IPv4 address>
(If the optional argument is not given, then the server will start on localhost)

To launch the client, run:
On windows:
python client_GUI.py
On linux:
python3 client_GUI.py


## COMPONENTS
server.py : The actual server class. Communicates with the DB (updates all messages there).
client.py: The client class, backend
client_GUI.py: The client class, frontend integrated with client.py
chatdb.py: Module for manipulating the database (write/read)


## CUSTOMIZING 
*Saved in firebase. You can change the certificate's path in chatdb.py

*libs has a nice looking theme I found on reddit. However, code should work without it!
Though UI won't looks as.


## A bit of extra info about the implementation 
1)The server does most of the heavy lifting:
For each connected client, it opens a thread for listening, and routes messages between clients.
A single thread is used for sending from server to clients (and updating DB). For efficiency, it usually sleeps, but when the queue for sending is filled a condition variable wakes it.
This also allows for a practically unbounded number of users, as required.


2) Each message sent by the client or sever is divided into size and message itself.
The message itself has a messagecode.
This implementation allows for super easy implementation of new features!


## External resources 
* Azure-ttk-theme-2.1.0. Found on reddit and github, improves the style of the GUI. In case it causes any errors, the project can work without it!
