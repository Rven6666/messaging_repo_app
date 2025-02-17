'''
app.py contains all of the server application
this is where you'll find all of the get/post request handlers
the socket event handlers are inside of socket_routes.py
''' 


import bcrypt
from flask import Flask, render_template, request, abort, url_for, session
from flask_socketio import SocketIO
from flask_login import LoginManager, logout_user, login_required, current_user
from flask_login import login_user as flask_user_login
from flask_wtf.csrf import CSRFProtect
import db
import secrets
import encyrption

import logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# this turns off Flask Logging, uncomment this to turn off Logging
# log = logging.getLogger('werkzeug')
# log.setLevel(logging.ERROR)

app = Flask(__name__)
csrf = CSRFProtect(app)
app.config['WTF_CSRF_CHECK_DEFAULT'] = True
app.config['WTF_CSRF_HEADERS'] = ["X-CSRFToken", "X-CSRF-Token"]

# secret key used to sign the session cookie
app.config['SECRET_KEY'] = secrets.token_hex()
socketio = SocketIO(app)

# don't remove this!!
import socket_routes

# index page
@app.route("/")
def index():
    return render_template("index.jinja")

conn_manage = LoginManager(app)
conn_manage.login_view = 'login'

# login page
@app.route("/login")
def login():
    return render_template("login.jinja")

# handles a post request when the user clicks the log in button
@app.route("/login/user", methods=["POST"])
def login_user():
    if not request.is_json:
        abort(404)

    username = request.json.get("username")

    user = db.get_user(username)
    if user is None:
        return "Error: User does not exist!"
    
    if not bcrypt.checkpw(request.json.get("password").encode('utf-8'), user.password):
        return "Error: Password does not match!"   
    
    flask_user_login(user)
    socketio.emit('user_change', {'action': 'login', 'username': username}, namespace='/')
    return url_for('home', username=request.json.get("username"))

@app.route('/logout')
def logout():
    username = current_user.username
    socketio.emit('user_change', {'action': 'logout', 'username': username}, namespace='/')
    logout_user()
    session.pop('room_id', None)
    return url_for('index')

@conn_manage.user_loader
def load_user(userName):
    user = db.get_user(userName)
    return user

# handles a get request to the signup page
@app.route("/signup")
def signup():
    return render_template("signup.jinja")

# handles a post request when the user clicks the signup button
@app.route("/signup/user", methods=["POST"])
def signup_user():
    bits = 10,
    if not request.is_json:
        abort(404)
    username = request.json.get("username")
    password = bcrypt.hashpw(request.json.get("password").encode('utf-8'), bcrypt.gensalt())
    #privateKey = encyrption.privateKey(bits[0])
    #print(privateKey)

    if db.get_user(username) is None:
        db.insert_user(username, password)
        return url_for('home', username=username)
    return "Error: User already exists!"

# handler when a "404" error happens
@app.errorhandler(404)
def page_not_found(_):
    return render_template('404.jinja'), 404

# home page, where the messaging app is
@app.route("/home")
@login_required
def home():
    if request.args.get("username") is None:
        abort(404)
    activ_user = db.get_conn_user()

    username = request.args.get("username")

    matches = db.friends_received(username)
    requests = db.show_friends_sent(username)
    friends_list = db.show_friends_list(username)

    return render_template("home.jinja", username=username,connected_users=activ_user, 
                           matches=matches, requests=requests, friendsList=friends_list)


# all functions for friends and requests:

#function to send friends reqursts
@app.route('/friend_request', methods=['POST'])
@login_required
def add_friend():
    friend = request.form.get('friend')
    sender = request.form.get('username')
    db.friend_request(sender, friend) 
    update_social_stats(sender, 'request_sent')
    return ('Friend request sent successfully!')    

#cancel a friends request
@app.route('/delete_request', methods=['POST'])
@login_required
def delete_user():
    friend = request.form.get('friend')
    username = request.form.get('username')
    db.cancel_request(username, friend)
    update_social_stats(username, 'request_deleted')
    return ('Request deleted successfully')  

#show friends
@app.route('/friends_list', methods=['POST'])
@login_required
def friends():
    friend1 = request.form.get('friend1')
    friend2 = request.form.get('friend2')
    db.friends(friend1, friend2) 
    update_social_stats(friend1, 'friend_added')
    return ('Friend added!')    

#remove friends 
@app.route('/remove_friends', methods=['POST'])
@login_required
def remove_friends():
    user = request.form.get('user')
    friend = request.form.get('friend')
    print(user, friend)
    result = db.remove_friends(user, friend) 
    update_social_stats(user, 'friend_removed')
    return result   

def update_social_stats(sender, update_type):
    """
    Emits a specialized Socket.IO message on friend-related changes.

    :param sender: The username of the person initiating the change.
    :param update_type: Type of update ('add', 'delete', etc.)
    """
    data = {
        'update_type': update_type,
        'sender': sender
    }
    friend_list = db.show_friends_list(sender)
    request_sent = db.show_friends_sent(sender)
    request_received = db.friends_received(sender)
    
    # Adding current user's friends and requests details to the data
    data.update({
        'friend_list': friend_list,
        'request_sent': request_sent,
        'request_received': request_received
    })
    logger.debug(f"\nApp: called update in frontend.\n")
    socketio.emit('social_update', data, namespace='/')

@app.after_request
def session_management(response):
    session.modified = True
    response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'SAMEORIGIN'
    response.headers['X-XSS-Protection'] = '1; mode=block'
    app.config['SESSION_COOKIE_HTTPONLY'] = True
    app.config['SESSION_COOKIE_SECURE'] = True
    app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
    return response

if __name__ == '__main__':
    ssl_cert = 'certs/info2222.crt'  # SSL certificate file
    ssl_key = 'certs/info2222.key'   # SSL private key file
    socketio.run(app, host='127.0.0.1', port=5000, ssl_context=(ssl_cert, ssl_key))
