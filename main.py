from pymongo import MongoClient
from bson import ObjectId
from flask import Flask, send_from_directory, request, jsonify
from threading import Thread
from werkzeug.security import generate_password_hash, check_password_hash
import jwt
import os
from datetime import datetime, timedelta
from functools import wraps
from renderchats import render_messages_html

# ==================== MongoDB Setup ====================
try:
    client = MongoClient("mongodb://localhost:27017/")
    db = client["chattersix_db"]
    users = db["users"]
    messages = db["messages"]
    chats = db["chats"]
    print("✓ Connected to MongoDB successfully!")
except Exception as e:
    print(f"✗ MongoDB connection failed: {e}")
    print("  Make sure MongoDB is running on localhost:27017")

SECRET_KEY = "your-secret-key-change-this-in-production"

# ==================== Helper Functions ====================
def create_token(username):
    """Create JWT token"""
    payload = {
        'username': username,
        'exp': datetime.utcnow() + timedelta(hours=24)
    }
    return jwt.encode(payload, SECRET_KEY, algorithm='HS256')

def verify_token(token):
    """Verify JWT token"""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=['HS256'])
        return payload['username']
    except:
        return None

def token_required(f):
    """Decorator to check if token is valid"""
    @wraps(f)
    def decorated(*args, **kwargs):
        token = request.headers.get('Authorization')
        if not token:
            return jsonify({'message': 'Token missing'}), 401
        
        token = token.split(' ')[1] if ' ' in token else token
        username = verify_token(token)
        if not username:
            return jsonify({'message': 'Invalid token'}), 401
        
        return f(username, *args, **kwargs)
    return decorated

# ==================== User WebUI (Port 5001) ====================
user_app = Flask("User WebUI", static_folder=None)

@user_app.route("/")
def user_index():
    return send_from_directory("web", "index.html")

@user_app.route("/login.html")
def user_login():
    return send_from_directory("web", "login.html")

@user_app.route("/register.html")
def user_register():
    return send_from_directory("web", "register.html")

@user_app.route("/<path:path>")
def user_static(path):
    return send_from_directory("web", path)

# API Routes for User WebUI
@user_app.route("/api/register", methods=["POST"])
def api_register():
    """Register a new user"""
    data = request.get_json()
    username = data.get('username', '').strip()
    email = data.get('email', '').strip()
    password = data.get('password', '')

    if not username or not email or not password:
        return jsonify({'message': 'Missing required fields'}), 400

    if len(password) < 6:
        return jsonify({'message': 'Password must be at least 6 characters'}), 400

    # Check if user already exists
    if users.find_one({'username': username}):
        return jsonify({'message': 'Username already exists'}), 400

    if users.find_one({'email': email}):
        return jsonify({'message': 'Email already exists'}), 400

    # Create new user
    hashed_password = generate_password_hash(password)
    user_doc = {
        'username': username,
        'email': email,
        'password': hashed_password,
        'created_at': datetime.utcnow(),
        'is_admin': False
    }
    users.insert_one(user_doc)

    return jsonify({'message': 'Registration successful'}), 201

@user_app.route("/api/login", methods=["POST"])
def api_login():
    """Login user"""
    data = request.get_json()
    username = data.get('username', '').strip()
    password = data.get('password', '')

    if not username or not password:
        return jsonify({'message': 'Missing username or password'}), 400

    user = users.find_one({'username': username})
    if not user or not check_password_hash(user['password'], password):
        return jsonify({'message': 'Invalid username or password'}), 401

    token = create_token(username)
    return jsonify({'token': token, 'username': username}), 200

@user_app.route("/api/me", methods=["GET"])
@token_required
def api_me(username):
    """Get current user info"""
    user = users.find_one({'username': username}, {'password': 0})
    if not user:
        return jsonify({'message': 'User not found'}), 404
    
    user['_id'] = str(user['_id'])
    return jsonify(user), 200

# ==================== Chat API Endpoints ====================
@user_app.route("/api/chats", methods=["GET"])
@token_required
def api_get_chats(username):
    """Get all chats for the current user"""
    try:
        user_chats = chats.find({'participants': username}).sort('updatedAt', -1)
        chat_list = []
        
        for chat in user_chats:
            chat_id_str = str(chat['_id'])

            last_read_map = chat.get('lastRead') or {}
            last_read = last_read_map.get(username)

            if last_read:
                unread_count = messages.count_documents({
                    'chatId': chat_id_str,
                    'timestamp': {'$gt': last_read}
                })
            else:
                unread_count = messages.count_documents({'chatId': chat_id_str})

            chat['_id'] = chat_id_str
            chat['unreadCount'] = unread_count
            chat_list.append(chat)
        
        return jsonify(chat_list), 200
    except Exception as e:
        return jsonify({'message': f'Error retrieving chats: {str(e)}'}), 500

@user_app.route("/api/chats", methods=["POST"])
@token_required
def api_create_chat(username):
    """Create a new chat"""
    try:
        data = request.get_json()
        name = data.get('name', 'New Chat').strip()
        participants = data.get('participants', [])
        
        if not participants:
            participants = [username]
        elif username not in participants:
            participants.append(username)
        
        chat_doc = {
            'name': name,
            'participants': participants,
            'createdBy': username,
            'createdAt': datetime.utcnow(),
            'updatedAt': datetime.utcnow(),
            'lastMessage': '',
            'messageCount': 0
        }
        
        result = chats.insert_one(chat_doc)
        chat_doc['_id'] = str(result.inserted_id)
        
        return jsonify(chat_doc), 201
    except Exception as e:
        return jsonify({'message': f'Error creating chat: {str(e)}'}), 500

@user_app.route("/api/chats/<chat_id>/messages", methods=["GET"])
@token_required
def api_get_messages(username, chat_id):
    """Get all messages in a chat"""
    try:
        from bson import ObjectId
        
        # Verify user is in chat
        chat = chats.find_one({'_id': ObjectId(chat_id)})
        if not chat or username not in chat.get('participants', []):
            return jsonify({'message': 'Unauthorized'}), 403
        
        # Get messages
        chat_messages = messages.find({'chatId': chat_id}).sort('timestamp', 1)
        message_list = []
        
        for msg in chat_messages:
            msg['_id'] = str(msg['_id'])
            message_list.append(msg)

        # Mark messages as read for this user (used for unread counts)
        chats.update_one(
            {'_id': ObjectId(chat_id)},
            {
                '$set': {
                    f'lastRead.{username}': datetime.utcnow()
                }
            }
        )

        return jsonify(message_list), 200
    except Exception as e:
        return jsonify({'message': f'Error retrieving messages: {str(e)}'}), 500


@user_app.route("/api/chats/<chat_id>/messages/render", methods=["GET"])
@token_required
def api_render_messages(username, chat_id):
    try:
        from bson import ObjectId

        chat = chats.find_one({'_id': ObjectId(chat_id)})
        if not chat or username not in chat.get('participants', []):
            return jsonify({'message': 'Unauthorized'}), 403

        chat_messages = list(messages.find({'chatId': chat_id}).sort('timestamp', 1))

        chats.update_one(
            {'_id': ObjectId(chat_id)},
            {
                '$set': {
                    f'lastRead.{username}': datetime.utcnow()
                }
            }
        )

        html = render_messages_html(chat_messages, username)
        return html, 200, {"Content-Type": "text/html; charset=utf-8"}
    except Exception as e:
        return jsonify({'message': f'Error rendering messages: {str(e)}'}), 500

@user_app.route("/api/chats/<chat_id>/messages", methods=["POST"])
@token_required
def api_send_message(username, chat_id):
    """Send a message in a chat"""
    try:
        from bson import ObjectId
        
        # Verify user is in chat
        chat = chats.find_one({'_id': ObjectId(chat_id)})
        if not chat or username not in chat.get('participants', []):
            return jsonify({'message': 'Unauthorized'}), 403
        
        data = request.get_json()
        text = data.get('text', '').strip()
        
        if not text:
            return jsonify({'message': 'Message cannot be empty'}), 400
        
        # Create message
        message_doc = {
            'chatId': chat_id,
            'sender': username,
            'text': text,
            'timestamp': datetime.utcnow()
        }
        
        result = messages.insert_one(message_doc)
        
        # Update chat's last message and timestamp
        chats.update_one(
            {'_id': ObjectId(chat_id)},
            {
                '$set': {
                    'lastMessage': text,
                    'updatedAt': datetime.utcnow()
                },
                '$inc': {'messageCount': 1}
            }
        )
        
        message_doc['_id'] = str(result.inserted_id)
        return jsonify(message_doc), 201
    except Exception as e:
        return jsonify({'message': f'Error sending message: {str(e)}'}), 500

def run_user():
    print("👥 User WebUI starting on http://localhost:5001")
    user_app.run(host="0.0.0.0", port=5001, debug=False)

# ==================== Admin Panel (Port 5000) ====================
admin_app = Flask("Admin Panel", static_folder=None)

@admin_app.route("/")
def admin_index():
    return send_from_directory("web-admin", "index.html")

@admin_app.route("/<path:path>")
def admin_static(path):
    return send_from_directory("web-admin", path)

def run_admin():
    print("� Admin Panel starting on http://localhost:5000")
    admin_app.run(host="0.0.0.0", port=5000, debug=False)

# ==================== Start Both Servers ====================
if __name__ == "__main__":
    print("\n" + "="*50)
    print("Chattersix Server Starting...")
    print("="*50 + "\n")
    
    # Run both Flask apps in separate threads
    admin_thread = Thread(target=run_admin, daemon=True)
    user_thread = Thread(target=run_user, daemon=True)
    
    admin_thread.start()
    user_thread.start()
    
    print("\n✓ Both servers are running!")
    print("  Admin Panel: http://localhost:5000")
    print("  User WebUI: http://localhost:5001")
    print("\nPress Ctrl+C to stop the server.\n")
    
    # Keep the main thread alive
    try:
        admin_thread.join()
    except KeyboardInterrupt:
        print("\n\nShutting down...")
        exit(0)

