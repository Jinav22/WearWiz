from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, send_from_directory, session
from werkzeug.utils import secure_filename
import os
import json
import requests
import asyncio
from datetime import datetime
import numpy as np
import logging

# Initialize logging
logging.basicConfig(level=logging.DEBUG)

app = Flask(__name__)
app.secret_key = 'your-secret-key'

# Configuration
UPLOAD_FOLDER = os.path.join('static', 'uploads')  # Relative to app root
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
API_BASE_URL = "http://localhost:8000"  # FastAPI service URL

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def get_user_metadata_path(username):
    # Create a metadata directory if it doesn't exist
    metadata_dir = 'user_metadata'
    os.makedirs(metadata_dir, exist_ok=True)
    return os.path.join(metadata_dir, f'{username}_metadata.json')

def load_clothing_data(username=None):
        # Load user-specific metadata
    try:
        with open(get_user_metadata_path(username), 'r') as f:
            data = json.load(f)
            return data if isinstance(data, list) else []
    except (FileNotFoundError, json.JSONDecodeError):
        return []


def save_clothing_data(data, username=None):
        # Save to user-specific metadata file
    with open(get_user_metadata_path(username), 'w') as f:
        json.dump(data, f, indent=2)


def load_users():
    try:
        with open('users.json', 'r') as f:
            return json.load(f)['users']
    except (FileNotFoundError, json.JSONDecodeError):
        return []

def save_users(users):
    with open('users.json', 'w') as f:
        json.dump({'users': users}, f)

def get_user_upload_path(username):
    return os.path.join('static', 'uploads', username)

@app.route('/upload', methods=['POST'])
def upload_file():
    if 'username' not in session:
        return jsonify({'error': 'Not logged in'}), 401
    
    if 'file' not in request.files:
        return jsonify({'error': 'No file selected'}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400

    if file and allowed_file(file.filename):
        try:
            filename = secure_filename(file.filename)
            base, ext = os.path.splitext(filename)
            counter = 1
            user_upload_path = get_user_upload_path(session['username'])
            
            while os.path.exists(os.path.join(user_upload_path, filename)):
                filename = f"{base}_{counter}{ext}"
                counter += 1

            os.makedirs(user_upload_path, exist_ok=True)
            file_path = os.path.join(user_upload_path, filename)
            file.save(file_path)
            
            # Load user-specific metadata
            clothing_data = load_clothing_data(session['username'])
            image_id = str(len(clothing_data) + 1)
            
            new_item = {
                'id': image_id,
                'image_id': image_id,
                'filename': filename,
                'path': f'uploads/{session["username"]}/{filename}',
                'title': "Processing...",
                'apparel_type': "Processing...",
                'description': "Processing...",
                'processing_status': 'pending',
                'username': session['username']
            }
            
            clothing_data.append(new_item)
            # Save to user-specific metadata file
            save_clothing_data(clothing_data, session['username'])
            
            # Start async processing
            try:
                response = requests.post(
                    f"{API_BASE_URL}/process-image/{image_id}",
                    params={"filename": filename, "image_path": file_path}
                )
                
                if response.status_code != 200:
                    print(f"Warning: Processing request failed with status {response.status_code}")
            except Exception as e:
                print(f"Warning: Failed to start processing: {e}")
                # Continue anyway since the image is uploaded
            
            return jsonify({
                'status': 'success',
                'message': 'File uploaded successfully',
                'image_id': image_id,
                'filename': filename,
                'path': f'uploads/{session["username"]}/{filename}'  # Return the path for immediate display
            })
                
        except Exception as e:
            return jsonify({'error': str(e)}), 500
    
    return jsonify({'error': 'Invalid file type'}), 400

@app.route('/check-processing-status/<image_id>')
def check_processing_status(image_id):
    try:
        response = requests.get(f"{API_BASE_URL}/processing-status/{image_id}")
        return jsonify(response.json())
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)})

@app.route('/')
def login():
    if 'username' in session:
        return redirect(url_for('gallery'))
    return render_template('login.html', users=load_users())

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        users = load_users()
        username = request.form['username']
        
        # Check if username already exists
        if any(user['username'] == username for user in users):
            flash('Username already exists')
            return redirect(url_for('register'))
        
        # Create new user
        new_user = {
            'username': username,
            'password': request.form['password'],  # Added password
            'name': request.form['name'],
            'age': request.form['age'],
            'gender': request.form['gender'],
            'country': request.form['country'],
            'occupation': request.form['occupation']
        }
        
        users.append(new_user)
        save_users(users)
        
        # Create user's upload directory
        os.makedirs(get_user_upload_path(username), exist_ok=True)
        
        flash('Registration successful! Please sign in.')
        return redirect(url_for('login'))
    
    return render_template('register.html')

@app.route('/login', methods=['POST'])
def handle_login():
    username = request.form['username']
    password = request.form['password']
    users = load_users()
    
    user = next((user for user in users if user['username'] == username), None)
    if user and user['password'] == password:  # Simple password check
        session['username'] = username
        return redirect(url_for('gallery'))
    
    flash('Invalid username or password')
    return redirect(url_for('login'))

@app.route('/logout')
def logout():
    session.pop('username', None)
    return redirect(url_for('login'))

@app.route('/gallery')
def gallery():
    if 'username' not in session:
        return redirect(url_for('login'))
    
    # Load user-specific clothing items
    user_items = load_clothing_data(session['username'])
    return render_template('gallery.html', items=user_items)

@app.route('/clear_all', methods=['POST'])
def clear_all():
    if 'username' not in session:
        return redirect(url_for('login'))
    
    username = session['username']
    
    # Clear user's metadata file
    save_clothing_data([], username)
    
    # Delete user's images
    user_uploads_dir = get_user_upload_path(username)
    if os.path.exists(user_uploads_dir):
        for filename in os.listdir(user_uploads_dir):
            if filename.endswith(('.png', '.jpg', '.jpeg', '.gif')):
                file_path = os.path.join(user_uploads_dir, filename)
                try:
                    os.remove(file_path)
                except Exception as e:
                    print(f"Error deleting {filename}: {e}")
    
    flash('All images and data have been cleared successfully.', 'success')
    return redirect(url_for('gallery'))

@app.route('/get-image-data/<image_id>')
def get_image_data(image_id):
    if 'username' not in session:
        return jsonify({'error': 'Not logged in'}), 401
        
    try:
        metadata = load_clothing_data(session['username'])
        for item in metadata:
            if str(item.get('id')) == str(image_id) or str(item.get('image_id')) == str(image_id):
                return jsonify({
                    'status': 'success',
                    'description': item['description'],
                    'title': item['title'],
                    'apparel_type': item['apparel_type'],
                    'filename': item['filename'],
                    'processing_status': item.get('processing_status', 'completed')
                })
        return jsonify({'status': 'error', 'message': 'Image data not found'}), 404
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/uploads/<path:filename>')
def serve_image(filename):
    return send_from_directory('uploads', filename)

# Add this route to serve static files during development
@app.route('/static/<path:filename>')
def serve_static(filename):
    return send_from_directory('static', filename)

# Add new route for recommendations page
@app.route('/recommendations')
def recommendations():
    if 'username' not in session:
        return redirect(url_for('login'))
    items = load_clothing_data(session['username'])
    return render_template('recommendations.html', items=items)

# Add route for random recommendation API
@app.route('/get-random-recommendation')
def get_random_recommendation():
    if 'username' not in session:
        return jsonify({'error': 'Not logged in'}), 401
    
    try:
        # Start async recommendation process
        response = requests.post(
            f"{API_BASE_URL}/generate-recommendation",
            json={"username": session['username']},  # Properly structure the JSON data
            headers={"Content-Type": "application/json"}
        )
        
        if response.status_code == 422:
            print(f"Validation error: {response.json()}")
            return jsonify({'status': 'error', 'error': 'Invalid request format'})
            
        return jsonify(response.json())
    except Exception as e:
        print(f"Recommendation error: {e}")
        return jsonify({'status': 'error', 'error': str(e)})

# Add this to your startup code


@app.route('/get-recommendation-for-apparel', methods=['POST'])
def get_recommendation_for_apparel():
    logging.debug("Received request to get recommendation for apparel")
    if 'username' not in session:
        return jsonify({'error': 'Not logged in'}), 401
    
    try:
        data = request.json
        # Start async recommendation process with specific apparel
        response = requests.post(
            f"{API_BASE_URL}/generate-recommendation-for-apparel",
            json={
                "username": session['username'],
                "image_id": data['imageId'],
                "description": data['description'],
                "apparel_type": data['apparelType']
            },
            headers={"Content-Type": "application/json"}
        )
        
        if response.status_code == 422:
            logging.error(f"Validation error: {response.json()}")
            return jsonify({'status': 'error', 'error': 'Invalid request format'})
            
        return jsonify(response.json())
    except Exception as e:
        logging.error(f"Error in get_recommendation_for_apparel: {e}")
        return jsonify({'status': 'error', 'error': str(e)})

@app.route('/get-recommendation-for-text', methods=['POST'])
def get_recommendation_for_text():
    logging.debug("Received request to get recommendation based on text")
    if 'username' not in session:
        return jsonify({'error': 'Not logged in'}), 401
    
    try:
        data = request.json
        input_text = data.get('input_text', '')
        if not input_text:
            return jsonify({'status': 'error', 'error': 'No input text provided'}), 400
        
        # Start async recommendation process with input text
        response = requests.post(
            f"{API_BASE_URL}/generate-recommendation-based-on-text",
            json={
                "username": session['username'],
                "input_text": input_text
            },
            headers={"Content-Type": "application/json"}
        )
        
        if response.status_code == 422:
            logging.error(f"Validation error: {response.json()}")
            return jsonify({'status': 'error', 'error': 'Invalid request format'})
            
        return jsonify(response.json())
    except Exception as e:
        logging.error(f"Error in get_recommendation_for_text: {e}")
        return jsonify({'status': 'error', 'error': str(e)})

if __name__ == '__main__':
    os.makedirs(UPLOAD_FOLDER, exist_ok=True)
    os.makedirs('user_metadata', exist_ok=True)
    app.run(debug=True) 