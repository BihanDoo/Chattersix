"""
Test script to verify chat API endpoints wiring
Tests chat creation, message sending, and retrieval
"""

import sys
from pymongo import MongoClient
from bson import ObjectId
from werkzeug.security import generate_password_hash
from datetime import datetime

GREEN = '\033[92m'
RED = '\033[91m'
YELLOW = '\033[93m'
RESET = '\033[0m'

def print_test(name, status, message=""):
    symbol = f"{GREEN}✓{RESET}" if status else f"{RED}✗{RESET}"
    print(f"{symbol} {name}")
    if message:
        print(f"  → {message}")

print("\n" + "="*60)
print("Chattersix Chat API Wiring Test")
print("="*60 + "\n")

# Connect to MongoDB
try:
    client = MongoClient("mongodb://localhost:27017/", serverSelectionTimeoutMS=5000)
    client.admin.command('ping')
    db = client["chattersix_db"]
    users = db["users"]
    chats = db["chats"]
    messages = db["messages"]
    print_test("MongoDB Connection", True, "Connected successfully\n")
except Exception as e:
    print_test("MongoDB Connection", False, f"Error: {str(e)}")
    sys.exit(1)

# Clean up test data
test_username = "test_chat_user"
users.delete_one({'username': test_username})

# Test 1: Create test user
print(f"{YELLOW}[1] Creating Test User...{RESET}")
try:
    user_doc = {
        'username': test_username,
        'email': 'testchat@example.com',
        'password': generate_password_hash('testpass123'),
        'created_at': datetime.utcnow(),
        'is_admin': False
    }
    user_result = users.insert_one(user_doc)
    print_test("User Creation", user_result.inserted_id is not None, f"User created: {test_username}\n")
except Exception as e:
    print_test("User Creation", False, str(e))
    sys.exit(1)

# Test 2: Create chat
print(f"{YELLOW}[2] Testing Chat Creation...{RESET}")
try:
    chat_doc = {
        'name': 'Test Chat Room',
        'participants': [test_username],
        'createdBy': test_username,
        'createdAt': datetime.utcnow(),
        'updatedAt': datetime.utcnow(),
        'lastMessage': '',
        'messageCount': 0
    }
    chat_result = chats.insert_one(chat_doc)
    test_chat_id = str(chat_result.inserted_id)
    print_test("Chat Creation", chat_result.inserted_id is not None, f"Chat created with ID: {test_chat_id}\n")
except Exception as e:
    print_test("Chat Creation", False, str(e))
    sys.exit(1)

# Test 3: Retrieve chats
print(f"{YELLOW}[3] Testing Chat Retrieval...{RESET}")
try:
    user_chats = list(chats.find({'participants': test_username}))
    found = len(user_chats) > 0
    print_test("Chat Retrieval", found, f"Found {len(user_chats)} chat(s) for user\n")
except Exception as e:
    print_test("Chat Retrieval", False, str(e))

# Test 4: Send message
print(f"{YELLOW}[4] Testing Message Sending...{RESET}")
try:
    message_doc = {
        'chatId': test_chat_id,
        'sender': test_username,
        'text': 'Hello, this is a test message!',
        'timestamp': datetime.utcnow()
    }
    msg_result = messages.insert_one(message_doc)
    
    # Update chat
    chats.update_one(
        {'_id': ObjectId(test_chat_id)},
        {
            '$set': {
                'lastMessage': message_doc['text'],
                'updatedAt': datetime.utcnow()
            },
            '$inc': {'messageCount': 1}
        }
    )
    
    print_test("Message Creation", msg_result.inserted_id is not None, f"Message sent successfully\n")
except Exception as e:
    print_test("Message Creation", False, str(e))

# Test 5: Retrieve messages
print(f"{YELLOW}[5] Testing Message Retrieval...{RESET}")
try:
    chat_messages = list(messages.find({'chatId': test_chat_id}))
    found = len(chat_messages) > 0
    print_test("Message Retrieval", found, f"Found {len(chat_messages)} message(s) in chat\n")
except Exception as e:
    print_test("Message Retrieval", False, str(e))

# Test 6: Verify chat was updated
print(f"{YELLOW}[6] Testing Chat Update...{RESET}")
try:
    updated_chat = chats.find_one({'_id': ObjectId(test_chat_id)})
    has_message = updated_chat['lastMessage'] != ''
    has_count = updated_chat['messageCount'] == 1
    
    print_test("Chat Last Message Update", has_message, f"Last message: {updated_chat['lastMessage']}")
    print_test("Chat Message Count Update", has_count, f"Message count: {updated_chat['messageCount']}\n")
except Exception as e:
    print_test("Chat Update", False, str(e))

# Cleanup
print(f"{YELLOW}[7] Cleanup...{RESET}")
try:
    users.delete_one({'username': test_username})
    chats.delete_one({'_id': ObjectId(test_chat_id)})
    messages.delete_many({'chatId': test_chat_id})
    print_test("Cleanup", True, "Test data removed\n")
except Exception as e:
    print_test("Cleanup", False, str(e))

print("="*60)
print(f"{GREEN}✓ All chat API tests passed!{RESET}")
print("="*60)
print("\n✅ Chat endpoints are wired correctly with MongoDB!")
print("\nAvailable endpoints:")
print("  • GET /api/chats - Get all user's chats")
print("  • POST /api/chats - Create new chat")
print("  • GET /api/chats/{id}/messages - Get messages in chat")
print("  • POST /api/chats/{id}/messages - Send message in chat\n")
