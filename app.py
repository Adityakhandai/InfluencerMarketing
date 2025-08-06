import os
import firebase_admin
from firebase_admin import credentials, auth, firestore
from flask import Flask, render_template, request, redirect, session, url_for, abort
from flask_mail import Mail, Message
import cloudinary
import cloudinary.uploader
import cloudinary.api


app = Flask(__name__)
app.secret_key = 'your-secret-key'  # Replace with a secure key in production

# Initialize Firebase Admin with your service account key
cred = credentials.Certificate("firebaseConfig.json")
firebase_admin.initialize_app(cred)
db = firestore.client()



cloudinary.config(
    cloud_name='dziaarqv8',
    api_key='195968372729411',
    api_secret='qKd__Yi61mQ6iN2SG6oKB0Y4bvs'
)

# Configure Flask-Mail (example using Gmail SMTP; update with your email credentials)
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 465
app.config['MAIL_USERNAME'] = 'sarkarmanish376@gmail.com'
app.config['MAIL_PASSWORD'] = 'Romanreings@123'
app.config['MAIL_USE_TLS'] = False
app.config['MAIL_USE_SSL'] = True
mail = Mail(app)

@app.route('/')
def index():
    # Check if user is logged in

    if 'user' in session:
        return redirect(url_for('dashboard'))
    else:
         return render_template('landing.html')
 

@app.route('/profile', methods=['GET', 'POST'])
def profile():
    # Check if user is logged in
    if 'user' not in session:
        return redirect(url_for('login'))
    
    # Ensure that only influencers can update their profile
    if session['user'].get('role') != 'influencer':
        return "Access denied. Only influencers can create posts."
    
    user = session['user']
    profiles_ref = db.collection('profiles')

    # Check if a profile for this user already exists
    existing_profile_docs = list(profiles_ref.where('user_id', '==', user['uid']).limit(1).stream())
    existing_profile = None

    if existing_profile_docs:
        existing_profile = existing_profile_docs[0].to_dict()
        existing_profile['id'] = existing_profile_docs[0].id
    
    if request.method == 'POST':
        # Get profile form fields from the request
        full_name = request.form.get('fullName')
        location = request.form.get('location')
        niche = request.form.get('niche')
        instagram_url = request.form.get('instagramUrl')
        twitter_url = request.form.get('twitterUrl')
        mail_id = request.form.get('mailId')
        instagram_followers = request.form.get('instagramFollowers')
        twitter_followers = request.form.get('twitterFollowers')

        # Initialize the profile data dictionary
        profile_data = {
            'full_name': full_name,
            'profile_pic_url': existing_profile['profile_pic_url'] if existing_profile and 'profile_pic_url' in existing_profile else '',
            'location': location,
            'niche': niche,
            'instagram_url': instagram_url,
            'twitter_url': twitter_url,
            'mail_id': mail_id,
            'instagram_followers': int(instagram_followers) if instagram_followers else 0,
            'twitter_followers': int(twitter_followers) if twitter_followers else 0,
            'user_id': user['uid'],
            'timestamp': firestore.SERVER_TIMESTAMP
        }

        # Check if a file was uploaded for profilePic
        if 'profilePic' in request.files:
            file_to_upload = request.files['profilePic']
            if file_to_upload.filename != "":
                try:
                    # Upload the file to Cloudinary
                    upload_result = cloudinary.uploader.upload(file_to_upload)
                    # Save the secure URL in the profile data
                    profile_data['profile_pic_url'] = upload_result.get('secure_url')
                except Exception as e:
                    print("Cloudinary upload failed:", e)
        
        # If profile exists, update it; otherwise, create a new profile
        if existing_profile:
            db.collection('profiles').document(existing_profile['id']).update(profile_data)
        else:
            db.collection('profiles').add(profile_data)
        
        return redirect(url_for('dashboard'))
    
    return render_template('profile.html', profile=existing_profile)



@app.route('/view_profile/<influencer_id>')
def view_profile(influencer_id):
    # Retrieve the influencer's profile from Firestore
    profiles_ref = db.collection('profiles')
    profile_query = profiles_ref.where('user_id', '==', influencer_id).limit(1).stream()
    profile = None
    for doc in profile_query:
        profile = doc.to_dict()
        profile['id'] = doc.id
    if not profile:
        return "Profile not found", 404

    # Retrieve posts created by this influencer
    posts_ref = db.collection('posts') \
        .where('user_id', '==', influencer_id) \
        .order_by('timestamp', direction=firestore.Query.DESCENDING)
    posts = []
    for doc in posts_ref.stream():
        post = doc.to_dict()
        post['id'] = doc.id
        posts.append(post)

    return render_template('view_profile.html', profile=profile, posts=posts)

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        role = request.form['role']  # 'influencer' or 'hire'
        try:
            # Create user in Firebase Authentication
            user = auth.create_user(email=email, password=password)
            # Store additional user data in Firestore
            db.collection('users').document(user.uid).set({
                'email': email,
                'role': role
            })
            return redirect(url_for('login'))
        except Exception as e:
            return f"Error during registration: {str(e)}"
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']  # Not used for verification in this demo
        try:
            # Fetch user by email using Firebase auth
            user = auth.get_user_by_email(email)
            # Retrieve user details from Firestore
            user_doc = db.collection('users').document(user.uid).get()
            if user_doc.exists:
                role = user_doc.get('role')
                session['user'] = {
                    'uid': user.uid,
                    'email': email,
                    'role': role
                    
                }
                # Redirect based on user role
                if role == 'hire':
                    return redirect(url_for('users'))
                else:
                    return redirect(url_for('dashboard'))
            else:
                return "User record not found in Firestore."
        except Exception as e:
            return f"Error during login: {str(e)}"
    return render_template('login.html')

@app.route('/dashboard')
def dashboard():
    if 'user' not in session:
        return redirect(url_for('login'))
    user = session['user']
    profile = None
    posts = []
    if user['role'] == 'influencer':
        # Retrieve the influencer's profile from Firestore
        profiles_ref = db.collection('profiles')
        profile_query = profiles_ref.where('user_id', '==', user['uid']).limit(1).stream()
        for doc in profile_query:
            profile = doc.to_dict()
            profile['id'] = doc.id
        
        # Get posts created by the current influencer
        posts_ref = db.collection('posts') \
            .where('user_id', '==', user['uid']) \
            .order_by('timestamp', direction=firestore.Query.DESCENDING)
        posts = [dict(doc.to_dict(), id=doc.id) for doc in posts_ref.stream()]
    return render_template('dashboard.html', user=user, posts=posts, profile=profile)

@app.route('/create_post', methods=['GET', 'POST'])
def create_post():
    if 'user' not in session:
        return redirect(url_for('login'))
    if session['user']['role'] != 'influencer':
        return "Access denied. Only influencers can create posts."
    if request.method == 'POST':
        title = request.form['title']
        description = request.form['description']
        post_data = {
            'title': title,
            'description': description,
            'user_id': session['user']['uid'],
            'timestamp': firestore.SERVER_TIMESTAMP
        }
        db.collection('posts').add(post_data)
        return redirect(url_for('dashboard'))
    return render_template('create_post.html')

@app.route('/delete_post/<post_id>', methods=['POST'])
def delete_post(post_id):
    if 'user' not in session:
        return redirect(url_for('login'))
    # Verify that the post belongs to the logged-in influencer
    post_ref = db.collection('posts').document(post_id)
    post = post_ref.get()
    if post.exists and post.to_dict().get('user_id') == session['user']['uid']:
        post_ref.delete()
        return redirect(url_for('dashboard'))
    else:
        return "You are not authorized to delete this post."

@app.route('/influencers')
def influencers():
    if 'user' not in session:
        return redirect(url_for('login'))

    influencers_list = []
    users_ref = db.collection('users').where('role', '==', 'influencer').stream()

    for doc in users_ref:
        user_data = doc.to_dict()

        profile_ref = db.collection('profiles').where('user_id', '==', doc.id).limit(1).stream()
        profile = None
        for profile_doc in profile_ref:
            profile = profile_doc.to_dict()

        influencers_list.append({
            'id': doc.id,
            'username': profile['full_name'] if profile and 'full_name' in profile else user_data.get('email', 'Unknown'),
        })


    return render_template('influencers.html', influencers=influencers_list)

# --- FIXED /users ROUTE ---
@app.route('/users')
def users():
    if 'user' not in session:
        return redirect(url_for('login'))
    
    # Get the minimum instagram followers threshold from the query parameter (default 0)
    try:
        min_instagram_followers = int(request.args.get('min_instagram_followers', 0))
    except ValueError:
        min_instagram_followers = 0

    # Get the search term from the query parameter (default empty string)
    search_term = request.args.get('search', '').strip().lower()

    influencers_list = []
    # Fetch all users from Firestore
    users_ref = db.collection('users').stream()

    for user_doc in users_ref:
        user_data = user_doc.to_dict()
        user_id = user_doc.id

        # Skip if not an influencer
        role = user_data.get('role', 'Unknown')
        if role.lower() != 'influencer':
            continue

        # Fetch corresponding profile, if it exists
        profile_query = db.collection('profiles').where('user_id', '==', user_id).limit(1).stream()
        profile_data = None
        for p_doc in profile_query:
            profile_data = p_doc.to_dict()

        # Extract influencer details (fallback to user_data if profile missing)
        if profile_data:
            full_name = profile_data.get('full_name', user_data.get('email', 'Unknown'))
            email = profile_data.get('mail_id', user_data.get('email', 'Unknown'))
            niche = profile_data.get('niche', 'Unknown')
            instagram_followers = profile_data.get('instagram_followers', 0)
            twitter_followers = profile_data.get('twitter_followers', 0)
            profile_pic_url = profile_data.get('profile_pic_url')
        else:
            full_name = user_data.get('email', 'Unknown')
            email = user_data.get('email', 'Unknown')
            niche = 'Unknown'
            instagram_followers = 0
            twitter_followers = 0
            profile_pic_url = None

        # Apply the Instagram followers filter
        if instagram_followers < min_instagram_followers:
            continue

        # Apply the search filter (searching in full name)
        if search_term and search_term not in full_name.lower():
            continue

        total_followers = instagram_followers + twitter_followers

        influencer = {
            'id': user_id,
            'username': full_name,
            'email': email,
            'role': role,
            'niche': niche,
            'followers': total_followers,
            'instagram_followers': instagram_followers,
            'profile_pic_url': profile_pic_url
        }
        influencers_list.append(influencer)

    return render_template('users.html', users=influencers_list)

@app.route('/chat/<influencer_id>')
def chat(influencer_id):
    if 'user' not in session:
        return redirect(url_for('login'))
    hire_id = session['user']['uid']

    # Create a unique chat ID by sorting the two user IDs
    chat_id = "-".join(sorted([influencer_id, hire_id]))

    # Ensure the chat document exists in Firestore
    chat_doc_ref = db.collection('chats').document(chat_id)
    chat_doc_ref.set({
        'participants': [influencer_id, hire_id],
        'created_at': firestore.SERVER_TIMESTAMP
    }, merge=True)

    # Render the chat page
    return render_template('chat.html', chat_id=chat_id, influencer_id=influencer_id, hire_id=hire_id)

@app.route('/chat_inbox')
def chat_inbox():
    if 'user' not in session:
        return redirect(url_for('login'))
    current_uid = session['user']['uid']
    user_chats = []
    # Fetch all chat documents and filter for chats including the current user
    chats_ref = db.collection("chats").stream()
    for doc in chats_ref:
        chat_id = doc.id
        if current_uid in chat_id.split("-"):
            ids = chat_id.split("-")
            partner_id = ids[0] if ids[1] == current_uid else ids[1]
            email_id = db.collection('users').document(partner_id).get().to_dict()['email']
            user_chats.append({'chat_id': chat_id, 'partner_id': partner_id, 'email_id': email_id})
    return render_template('chat_inbox.html', chats=user_chats)

@app.route('/send_chat_email/<partner_id>')
def send_chat_email(partner_id):
    if 'user' not in session:
        return redirect(url_for('login'))
    user_id = session['user']['uid']
    # Create a chat ID (assuming a two-person chat)
    chat_id = "-".join(sorted([partner_id, user_id]))
    chat_url = url_for('chat', influencer_id=partner_id, _external=True)
    try:
        msg = Message("Chat Invitation",
                      sender=app.config['MAIL_USERNAME'],
                      recipients=[session['user']['email']])
        msg.body = f"Click the following link to open your chat: {chat_url}"
        mail.send(msg)
        return "Chat email sent!"
    except Exception as e:
        return f"Error sending email: {str(e)}"

@app.route('/logout')
def logout():
    session.pop('user', None)
    return redirect(url_for('login'))

if __name__ == '__main__':
    app.run(debug=True)
