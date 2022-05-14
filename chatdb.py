import firebase_admin
from firebase_admin import credentials
from firebase_admin import firestore
from datetime import datetime
import random


CONST_MAX = 0xffffffff

#Setup
certificate_path = None #ADD YOU CERTIFICATE HERE!
cred = credentials.Certificate(certificate_path)
firebase_admin.initialize_app(cred)
db = firestore.client()
chats_collection = db.collection(u"chats")


def new_chat_dict(HOST, PORT, time):
    return {"Host":HOST, "Port":PORT, u"Start_time":time}

#Create a new chat in the DB. To be called from server.
def new_chat(sockname):
    try:
        HOST = sockname[0]
        PORT = sockname[1]
        timestamp = datetime.today().strftime('%Y-%m-%d_%H:%M:%S')
        chat_name = f"({HOST},{PORT}_{timestamp}_{random.randint(0,CONST_MAX)})"
        chat = chats_collection.document(chat_name)
        chat.set(new_chat_dict(HOST,PORT,timestamp))
        chat.collection("messages").document("Init").set({u"msg_id":-1})
        return chat_name
    except:
        print("Error: could not initializie database. Chat will not be saved")
        return None

#Add a message to chat_name chat in the db
def add_message(chat_name, msgcode, src_addr, src_name, msg_id, codes_to_ignore, msg=None):
    if not (msgcode in codes_to_ignore):
        try:
            messages_collection = chats_collection.document(chat_name).collection("messages")
            messages_collection.document(f"msg_{msg_id}").set({
                u"timestamp":firestore.SERVER_TIMESTAMP,
                u"msgcode":msgcode,
                u"src_addr":src_addr,
                u"src_name":src_name,
                u"msg_id":msg_id,
                u"msg":msg
            })
        except:
            print("Error: failed to log message")

#Get all chats in the db, by start time
def get_all_chats():
    query = chats_collection.order_by(u'Start_time')
    results = query.stream()
    return [res.id for res in results]

#Get all messages in chat chat_name
def get_all_messages(chat_name):
    messages_collection = chats_collection.document(chat_name).collection("messages")
    query = messages_collection.where(u"msg_id",u">",-1).order_by(u"msg_id")
    results = query.stream()
    return [(message.get("msgcode"),message.get("src_name"),message.get("msg")) for message in results]


if __name__ == "__main__":
    messages = get_all_messages("(0.0.0.0,27000_2022-04-29_00:25:31_537023147)")
    print(messages)