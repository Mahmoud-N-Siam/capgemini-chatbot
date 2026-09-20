from flask import Blueprint, render_template

web_routes = Blueprint('web', __name__)

@web_routes.route('/')
def index():
    return render_template('index.html')

@web_routes.route('/chat')
def chat_page():
    return render_template('chat.html')