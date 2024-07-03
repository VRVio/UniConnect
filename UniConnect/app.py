from flask import Flask, request, render_template, redirect, session, jsonify
from flask_sqlalchemy import SQLAlchemy
import bcrypt
from datetime import datetime
import humanize
import re

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database.db'
db = SQLAlchemy(app)
app.secret_key = 'batman'

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    usn = db.Column(db.String(100), unique=True, nullable=False)
    password = db.Column(db.String(100), nullable=False)

    def __init__(self, name, usn, password):
        self.name = name
        self.usn = usn
        self.password = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

    def check_password(self, password):
        return bcrypt.checkpw(password.encode('utf-8'), self.password.encode('utf-8'))

class Post(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    content = db.Column(db.Text, nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    user_name = db.Column(db.String(100), nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    parent_id = db.Column(db.Integer, db.ForeignKey('post.id'), nullable=True)
    parent = db.relationship('Post', remote_side=[id], backref='comments')
    tags = db.Column(db.String, nullable=True)

    def __init__(self, title, content, user_id, user_name, parent_id=None, tags=None):
        self.title = title
        self.content = content
        self.user_id = user_id
        self.user_name = user_name
        self.parent_id = parent_id
        self.tags = tags

class Notification(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    message = db.Column(db.String(255), nullable=False)
    post_id = db.Column(db.Integer, nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    read = db.Column(db.Boolean, default=False)

    def __init__(self, user_id, message, post_id):
        self.user_id = user_id
        self.message = message
        self.post_id = post_id

class Comment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.Text, nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    user_name = db.Column(db.String(100), nullable=False)
    post_id = db.Column(db.Integer, db.ForeignKey('post.id'), nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

    def __init__(self, content, user_id, user_name, post_id):
        self.content = content
        self.user_id = user_id
        self.user_name = user_name
        self.post_id = post_id

with app.app_context():
    db.create_all()

@app.route('/', methods=['GET', 'POST'])
def home():
    return render_template('Home.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        if 'name' in request.form:
            try:
                name = request.form['name']
                usn = request.form['usn']
                password = request.form['password']
                if not name or not usn or not password:
                    return "All fields are required!", 400
                new_user = User(name=name, usn=usn, password=password)
                db.session.add(new_user)
                db.session.commit()
                return redirect('/register')
            except Exception as e:
                db.session.rollback()
                return str(e), 500
        else:
            usn = request.form['usn']
            password = request.form['password']
            user = User.query.filter_by(usn=usn).first()
            if user and user.check_password(password):
                session['usn'] = user.usn
                return redirect('/dashboard')
            else:
                return "Invalid credentials, Go Back", 401
    return render_template('register.html')

@app.route('/dashboard')
def render_dashboard():
    if 'usn' in session:
        user = User.query.filter_by(usn=session['usn']).first()
        return render_template('dbafterlogin.html', user=user)
    return redirect('/register')

@app.route('/create_post', methods=['POST'])
def create_post():
    if 'usn' not in session:
        return redirect('/register')
    
    title = request.form['title']
    content = request.form['content']
    user = User.query.filter_by(usn=session['usn']).first()

    if not title or not content:
        return "Title and Content are required!", 400

    new_post = Post(title=title, content=content, user_id=user.usn, user_name=user.name)
    db.session.add(new_post)
    db.session.commit()

    tagged_users = re.findall(r'@(\w+)', content)
    for usn in tagged_users:
        tagged_user = User.query.filter_by(usn=usn).first()
        if tagged_user:
            notification = Notification(user_id=tagged_user.id, message=f"You were tagged in a post by {user.name}", post_id=new_post.id)
            db.session.add(notification)
    
    db.session.commit()
    
    return redirect('/dashboard')

@app.route('/profile', methods=['GET'])
def profile():
    if 'usn' not in session:
        return redirect('/register')
    
    user = User.query.filter_by(usn=session['usn']).first()
    posts = Post.query.filter_by(user_id=session['usn']).all()
    for post in posts:
        post.humanized_time = humanize.naturaltime(post.timestamp)

    return render_template('profile.html', user=user, posts=posts)

@app.route('/add_comment/<int:post_id>', methods=['POST'])
def add_comment(post_id):
    if 'usn' not in session:
        return redirect('/register')

    content = request.form['content']
    user = User.query.filter_by(usn=session['usn']).first()
    post = Post.query.get_or_404(post_id)

    if not content:
        return "Content is required!", 400

    new_comment = Comment(content=content, user_id=user.id, user_name=user.name, post_id=post_id)
    db.session.add(new_comment)
    db.session.commit()
    notification_message = f"New comment on your post '{post.title}'"
    notification = Notification(user_id=post.user_id, post_id=post_id, message=notification_message)
    db.session.add(notification)
    db.session.commit()
    return redirect('/post/' + str(post_id))

@app.route('/get_posts', methods=['GET'])
def get_posts():
    if 'usn' not in session:
        return redirect('/register')

    posts = Post.query.order_by(Post.timestamp.desc()).all()
    now = datetime.utcnow()
    return jsonify([{
        'title': post.title,
        'content': post.content,
        'timestamp': humanize.naturaltime(now - post.timestamp),
        'username': post.user_name,
        'user_id': post.user_id,
        'id': post.id
    } for post in posts])

@app.route('/logout')
def logout():
    session.pop('usn', None)
    return redirect('/register')

@app.route('/post/<int:post_id>', methods=['GET'])
def view_post(post_id):
    if 'usn' not in session:
        return redirect('/register')
    
    post = Post.query.get(post_id)
    if not post:
        return "Post not found!", 404
    
    user = User.query.filter_by(usn=session['usn']).first()
    
    comments = Comment.query.filter_by(post_id=post_id).order_by(Comment.timestamp.asc()).all()
    
    for comment in comments:
        comment.humanized_time = humanize.naturaltime(comment.timestamp)
    
    return render_template('post.html', post=post, comments=comments, user=user)

@app.route('/delete-post/<int:post_id>', methods=['DELETE'])
def delete_post(post_id):
    if 'usn' not in session:
        return jsonify({"error": "Unauthorized"}), 401
    
    post = Post.query.filter_by(id=post_id).first()
    if not post:
        return jsonify({"error": "Post not found"}), 404
    
    if post.user_id != session['usn']:
        return jsonify({"error": "Unauthorized to delete this post"}), 403

    db.session.delete(post)
    db.session.commit()

    return jsonify({"message": "Post deleted successfully"}), 200

@app.route('/notifications', methods=['GET'])
def notifications():
    if 'usn' not in session:
        return jsonify({"error": "Unauthorized"}), 401

    user = User.query.filter_by(usn=session['usn']).first()
    notifications = Notification.query.filter_by(user_id=user.id, read=False).order_by(Notification.timestamp.desc()).all()

    notification_list = []
    for notification in notifications:
        post = Post.query.get(notification.post_id)
        if post:
            notification_list.append({
                'id': notification.id,
                'message': notification.message,
                'timestamp': humanize.naturaltime(notification.timestamp),
                'post_id': post.id,
                'post_title': post.title,
                'tagged_by': notification.message.split(' ')[-1]
            })

    return jsonify(notification_list)

app.run(debug=False,host='0.0.0.0')
