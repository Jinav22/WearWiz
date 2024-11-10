from groq import Groq
import os
import json
import base64
from PIL import Image
from concurrent.futures import ThreadPoolExecutor
import threading
import queue
import chromadb
from chromadb.config import Settings
from fashion_clip.fashion_clip import FashionCLIP
import numpy as np
import datetime
import random

# Initialize clients and models
client = Groq(api_key="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")
fclip = FashionCLIP('fashion-clip')
chroma_client = chromadb.Client(Settings(
    persist_directory="./vector_db",
    is_persistent=True
))

# Initialize thread pool executor and processing queue
executor = ThreadPoolExecutor(max_workers=3)
processing_queue = queue.Queue()

def get_user_collection(username):
    """Get or create user-specific ChromaDB collection"""
    collection_name = f"fashion_items_{username}"
    try:
        return chroma_client.get_collection(name=collection_name)
    except ValueError:
        return chroma_client.create_collection(
            name=collection_name,
            metadata={"hnsw:space": "cosine", "username": username}
        )

def get_user_category_collection(username, category):
    """Get or create user and category specific ChromaDB collection"""
    collection_name = f"fashion_items_{username}_{category}"
    try:
        return chroma_client.get_collection(name=collection_name)
    except Exception as e:
        print(f"Collection {collection_name} not found.. creating the collection")
        return chroma_client.create_collection(
            name=collection_name,
            metadata={"hnsw:space": "cosine", "username": username, "category": category}
        )

def generate_embeddings(image_path, description):
    """Generate embeddings for both image and text"""
    try:
        # Generate image embeddings
        image = Image.open(image_path)
        image_embeddings = fclip.encode_images([image], batch_size=1)[0]
        
        # Generate text embeddings
        text_embeddings = fclip.encode_text([description], batch_size=1)[0]
        
        # Normalize embeddings
        image_embeddings = image_embeddings/np.linalg.norm(image_embeddings)
        text_embeddings = text_embeddings/np.linalg.norm(text_embeddings)
        
        return {
            'image_embedding': image_embeddings.tolist(),
            'text_embedding': text_embeddings.tolist(),
            'timestamp': str(datetime.datetime.now())
        }
    except Exception as e:
        print(f"Error generating embeddings: {e}")
        return None

def store_embeddings(username, image_id, embeddings, description, filename, category):
    """Store embeddings in user's category-specific ChromaDB collection"""
    try:
        # Get or create category-specific collection
        collection_name = f"fashion_items_{username}_{category}"
        try:
            collection = chroma_client.get_collection(name=collection_name)
            print(f"Collection {collection_name} already exists")
        except Exception as e:
            print(f"Creating new collection for user {username} and category {category}")
            collection = chroma_client.create_collection(
                name=collection_name,
                metadata={
                    "hnsw:space": "cosine", 
                    "username": username,
                    "category": category
                }
            )
        
        # Store embeddings with metadata
        collection.add(
            embeddings=[embeddings['image_embedding']],
            documents=[description],
            metadatas=[{
                "image_id": image_id,
                "filename": filename,
                "timestamp": embeddings['timestamp'],
                "username": username,
                "category": category
            }],
            ids=[f"{username}_{category}_{image_id}"]
        )
        print(f"Stored embeddings for image {image_id} in collection {collection_name}")
        return True
    except Exception as e:
        print(f"Error storing embeddings: {e}")
        return False

def get_user_metadata_path(username):
    """Get path to user's metadata file"""
    metadata_dir = 'user_metadata'
    os.makedirs(metadata_dir, exist_ok=True)
    return os.path.join(metadata_dir, f'{username}_metadata.json')

def find_image_owner(image_id: str):
    """Find which user owns a specific image"""
    metadata_dir = 'user_metadata'
    print(f"Searching for owner of image {image_id}")
    
    if os.path.exists(metadata_dir):
        for metadata_file in os.listdir(metadata_dir):
            if not metadata_file.endswith('_metadata.json'):
                continue
            
            username = metadata_file.replace('_metadata.json', '')
            metadata_path = os.path.join(metadata_dir, metadata_file)
            print(f"Checking metadata file: {metadata_path}")
            
            try:
                with open(metadata_path, 'r') as f:
                    metadata = json.load(f)
                    for item in metadata:
                        # Check both username and image_id
                        if (str(item.get('image_id')) == str(image_id) and 
                            item.get('username') == username):
                            print(f"Found owner {username} for image {image_id}")
                            return username
            except (json.JSONDecodeError, FileNotFoundError) as e:
                print(f"Error reading metadata file {metadata_path}: {e}")
                continue
    print(f"No owner found for image {image_id}")
    return None

def encode_image(image_path):
    """Encode image to base64 string"""
    with open(image_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode('utf-8')

def generate_description(image_path):
    """Generate description using Llama Vision via Groq"""
    try:
        base64_image = encode_image(image_path)
        
        chat_completion = client.chat.completions.create(
            model="llama-3.2-90b-vision-preview",
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": "Provide a one-line, highly detailed description of the apparel that highlights unique features, style, and any distinguishing patterns or colors. Make the description precise and unique enough to easily identify this item among similar apparel. Don't give details that are not visible. Return only the descriptive phrase in one line."
                        },
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{base64_image}"
                            }
                        }
                    ]
                }
            ]
        )
        
        return chat_completion.choices[0].message.content.strip()
        
    except Exception as e:
        print(f"Error generating description: {e}")
        return "Error generating description"

def update_metadata(image_id: str, description: str, filename: str = None):
    """Update metadata in user's file"""
    username = find_image_owner(image_id)
    if not username:
        print(f"Could not find owner for image {image_id}")
        return False
        
    metadata_path = get_user_metadata_path(username)
    print(f"Updating metadata at: {metadata_path}")
    
    try:
        # Ensure the file exists with at least an empty array
        if not os.path.exists(metadata_path):
            with open(metadata_path, 'w') as f:
                json.dump([], f)
        
        with open(metadata_path, 'r') as f:
            metadata = json.load(f)
            
        found = False
        for item in metadata:
            if str(item.get('image_id')) == str(image_id):
                item['description'] = description
                item['processing_status'] = 'completed'
                found = True
                break
                
        if not found:
            print(f"WARNING: Image {image_id} not found in metadata file")
            return False
                
        with open(metadata_path, 'w') as f:
            json.dump(metadata, f, indent=2)
        print(f"Successfully updated metadata for image {image_id}")
        return True
                
    except Exception as e:
        print(f"Error updating metadata: {e}")
        return False

def generate_title(image_path):
    """Generate a short title for the apparel"""
    try:
        base64_image = encode_image(image_path)
        
        chat_completion = client.chat.completions.create(
            model="llama-3.2-90b-vision-preview",
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": "Give a very short 2-4 word title for this apparel item. Make it concise and descriptive. Return only the title."
                        },
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{base64_image}"
                            }
                        }
                    ]
                }
            ]
        )
        
        return chat_completion.choices[0].message.content.strip()
        
    except Exception as e:
        print(f"Error generating title: {e}")
        return "Untitled Item"

def determine_apparel_type(image_path):
    """Determine the type of apparel from predefined categories"""
    try:
        base64_image = encode_image(image_path)
        
        chat_completion = client.chat.completions.create(
            model="llama-3.2-90b-vision-preview",
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": "What type of apparel is this? Choose exactly one category from: [top, bottom, outerwear, full-body]. Return only the category name in lowercase."
                        },
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{base64_image}"
                            }
                        }
                    ]
                }
            ]
        )
        
        apparel_type = chat_completion.choices[0].message.content.strip().lower()
        valid_types = ['top', 'bottom', 'outerwear', 'full-body']
        return apparel_type if apparel_type in valid_types else 'top'
        
    except Exception as e:
        print(f"Error determining apparel type: {e}")
        return 'top'

def process_in_background(image_id, filename, image_path):
    """Background processing function with ordered steps"""
    try:
        print(f"Starting background processing for image {image_id}")
        
        # Extract username from image_path
        path_parts = image_path.split(os.sep)
        username = path_parts[-2] if len(path_parts) >= 3 else None
        
        if not username:
            print(f"ERROR: Could not extract username from path {image_path}")
            return False
            
        print(f"Found username from path: {username}")
        
        # Step 1: Generate description
        print(f"Step 1: Generating description for image {image_id}")
        description = generate_description(image_path)
        print(f"Generated description: {description}")
        
        # Step 2: Generate title
        print(f"Step 2: Generating title for image {image_id}")
        title = generate_title(image_path)
        print(f"Generated title: {title}")
        
        # Step 3: Determine apparel type/category
        print(f"Step 3: Determining apparel type for image {image_id}")
        apparel_type = determine_apparel_type(image_path)
        print(f"Determined type: {apparel_type}")
        
        # Step 4: Update metadata with generated information
        metadata_path = get_user_metadata_path(username)
        try:
            with open(metadata_path, 'r') as f:
                metadata = json.load(f)
                
            for item in metadata:
                if str(item.get('image_id')) == str(image_id):
                    item['description'] = description
                    item['title'] = title
                    item['apparel_type'] = apparel_type
                    item['processing_status'] = 'processing_embeddings'
                    break
                    
            with open(metadata_path, 'w') as f:
                json.dump(metadata, f, indent=2)
                
            print(f"Successfully updated metadata for image {image_id}")
            
            # Step 5: Generate embeddings
            print(f"Step 5: Generating embeddings for image {image_id}")
            image = Image.open(image_path)
            image_embedding = fclip.encode_images([image], batch_size=1)[0]
            normalized_image_embedding = image_embedding/np.linalg.norm(image_embedding)
            
            # Step 6: Store embeddings in category-specific collection
            print(f"Step 6: Storing embeddings in {apparel_type} collection")
            collection = get_user_category_collection(username, apparel_type)
            print("Created!")
            collection.add(
                embeddings=[normalized_image_embedding.tolist()],  # Store normalized image embedding
                documents=[description],
                metadatas=[{
                    "image_id": image_id,
                    "filename": filename,
                    "timestamp": str(datetime.datetime.now()),
                    "username": username,
                    "category": apparel_type
                }],
                ids=[f"{username}_{apparel_type}_{image_id}"]
            )
            
            # Update processing status to completed
            for item in metadata:
                if str(item.get('image_id')) == str(image_id):
                    item['processing_status'] = 'completed'
                    break
                    
            with open(metadata_path, 'w') as f:
                json.dump(metadata, f, indent=2)
                
            print(f"Successfully completed processing for image {image_id}")
            return True
            
        except Exception as e:
            print(f"Error updating metadata: {e}")
            return False
            
    except Exception as e:
        print(f"Error in background processing for image {image_id}: {e}")
        return False

# def find_similar_items(username, image_path, limit=5):
#     """Find similar items in user's collection"""
#     try:
#         # Generate query image embeddings
#         image = Image.open(image_path)
#         query_embedding = fclip.encode_images([image])[0].tolist()
        
#         # Query user's collection
#         collection = get_user_collection(username)
#         results = collection.query(
#             query_embeddings=[query_embedding],
#             n_results=limit,
#             include=['metadatas', 'documents', 'distances']
#         )
        
#         # Format results
#         similar_items = []
#         for i in range(len(results['ids'][0])):
#             similar_items.append({
#                 'image_id': results['metadatas'][0][i]['image_id'],
#                 'filename': results['metadatas'][0][i]['filename'],
#                 'description': results['documents'][0][i],
#                 'similarity': 1 - results['distances'][0][i]
#             })
        
#         return similar_items
#     except Exception as e:
#         print(f"Error finding similar items: {e}")
#         return []

# Add these to initialize at startup
def init_vector_db():
    """Initialize vector database directory"""
    os.makedirs('./vector_db', exist_ok=True)
    print("Vector database initialized")

# Call this when starting the application
init_vector_db()

def generate_outfit_recommendation(username):
    """Generate outfit recommendation starting with a random bottom"""
    try:
        print(f"Generating outfit recommendation for user {username}")
        
        # Get user's metadata
        metadata_path = get_user_metadata_path(username)
        with open(metadata_path, 'r') as f:
            metadata = json.load(f)
            
        if not metadata:
            return {"status": "error", "error": "No items found"}
            
        # Filter bottoms only
        bottom_items = [item for item in metadata if item['apparel_type'] == 'bottom']
        if not bottom_items:
            return {"status": "error", "error": "No bottom apparel found"}
            
        # 1. Select random bottom item
        selected_bottom = random.choice(bottom_items)
        bottom_description = selected_bottom['description']
        print(f"Selected bottom description: {bottom_description}")

        # 2. Generate compatible top description using LLM
        prompt = f"""Given this bottom apparel: "{bottom_description}"
        Suggest a compatible top that would create a stylish outfit.
        Consider color coordination, style matching, and overall aesthetic harmony.
        Return only a single-line detailed description of the ideal top piece."""

        chat_completion = client.chat.completions.create(
            model="llama-3.2-90b-text-preview",
            messages=[{"role": "user", "content": prompt}]
        )
        generated_top_description = chat_completion.choices[0].message.content.strip()
        print(f"Generated top description: {generated_top_description}")

        # Convert text description to embedding and query TOP collection
        text_embedding = fclip.encode_text([generated_top_description], batch_size=1)[0]
        normalized_embedding = text_embedding/np.linalg.norm(text_embedding)
        
        # Query TOP collection with embedding (since we started with bottom)
        tops_collection = get_user_category_collection(username, 'top')  # Explicitly query tops
        results = tops_collection.query(
            query_embeddings=[normalized_embedding.tolist()],
            n_results=1,
            include=['metadatas', 'documents']
        )

        if not results['metadatas'][0]:
            return {"status": "error", "error": "No matching top found"}

        best_match_metadata = results['metadatas'][0][0]
        best_match = next(
            (item for item in metadata if str(item['image_id']) == str(best_match_metadata['image_id'])), 
            None
        )

        if not best_match:
            return {"status": "error", "error": "Could not find matching item metadata"}

        # 4. Update pairs arrays in metadata
        if 'pairs' not in selected_bottom:
            selected_bottom['pairs'] = []
        if 'pairs' not in best_match:
            best_match['pairs'] = []

        # Add new pairing
        if str(best_match['image_id']) not in selected_bottom['pairs']:
            selected_bottom['pairs'].append(str(best_match['image_id']))
        if str(selected_bottom['image_id']) not in best_match['pairs']:
            best_match['pairs'].append(str(selected_bottom['image_id']))

        # Save updated metadata
        with open(metadata_path, 'w') as f:
            json.dump(metadata, f, indent=2)

        return {
            "status": "success",
            "base_item": {
                "image_url": f"/static/uploads/{username}/{selected_bottom['filename']}",
                "description": selected_bottom['description'],
                "title": selected_bottom['title'],
                "type": selected_bottom['apparel_type']
            },
            "recommended_item": {
                "image_url": f"/static/uploads/{username}/{best_match['filename']}",
                "description": best_match['description'],
                "title": best_match['title'],
                "type": best_match['apparel_type']
            }
        }
        
    except Exception as e:
        print(f"Error generating recommendation: {e}")
        return {"status": "error", "error": str(e)}

def generate_outfit_recommendation_for_apparel(username, image_id, description, apparel_type):
    """Generate outfit recommendation based on specific apparel"""
    try:
        print(f"Generating recommendation for {apparel_type} item: {image_id}")
        
        # Get user's metadata
        metadata_path = get_user_metadata_path(username)
        with open(metadata_path, 'r') as f:
            metadata = json.load(f)
            
        if not metadata:
            return {"status": "error", "error": "No items found"}
            
        # Get base item
        base_item = next((item for item in metadata if str(item['image_id']) == str(image_id)), None)
        if not base_item:
            return {"status": "error", "error": "Selected item not found"}
            
        # Determine target category based on selected apparel type
        target_category = 'bottom' if apparel_type in ['top', 'outerwear'] else 'top'
        
        # Generate prompt for complementary item
        prompt = f"""Given this {apparel_type}: "{description}"
        Suggest a complementary {target_category} that would create a stylish outfit.
        Consider color coordination, style matching, and overall aesthetic harmony.
        Return only a single-line detailed description of the ideal {target_category} piece."""
        
        # Get suggestion from LLM
        chat_completion = client.chat.completions.create(
            model="llama-3.2-90b-text-preview",
            messages=[{"role": "user", "content": prompt}]
        )
        
        suggested_description = chat_completion.choices[0].message.content.strip()
        print(f"Generated {target_category} description: {suggested_description}")
        print(f"Target category: {target_category}")
        print(f"Base item: {apparel_type}")
        
        # Convert suggested description to embedding
        text_embedding = fclip.encode_text([suggested_description], batch_size=1)[0]
        normalized_embedding = text_embedding/np.linalg.norm(text_embedding)
        
        # Query complementary category collection
        complementary_collection = get_user_category_collection(username, target_category)  # Explicitly query complementary category
        results = complementary_collection.query(
            query_embeddings=[normalized_embedding.tolist()],
            n_results=1,
            include=['metadatas', 'documents']
        )
        
        if not results['metadatas'][0]:
            return {
                "status": "error", 
                "error": f"No matching {target_category} found in your wardrobe"
            }

        recommended_metadata = results['metadatas'][0][0]
        recommended_item = next(
            (item for item in metadata if str(item['image_id']) == str(recommended_metadata['image_id'])), 
            None
        )

        if not recommended_item:
            return {"status": "error", "error": "Could not find matching item metadata"}
        
        # Update pairs in metadata
        if 'pairs' not in base_item:
            base_item['pairs'] = []
        if 'pairs' not in recommended_item:
            recommended_item['pairs'] = []

        # Add new pairing
        if str(recommended_item['image_id']) not in base_item['pairs']:
            base_item['pairs'].append(str(recommended_item['image_id']))
        if str(base_item['image_id']) not in recommended_item['pairs']:
            recommended_item['pairs'].append(str(base_item['image_id']))

        # Save updated metadata
        with open(metadata_path, 'w') as f:
            json.dump(metadata, f, indent=2)
        
        return {
            "status": "success",
            "base_item": {
                "image_url": f"/static/uploads/{username}/{base_item['filename']}",
                "description": base_item['description'],
                "title": base_item['title'],
                "type": base_item['apparel_type']
            },
            "recommended_item": {
                "image_url": f"/static/uploads/{username}/{recommended_item['filename']}",
                "description": recommended_item['description'],
                "title": recommended_item['title'],
                "type": recommended_item['apparel_type']
            }
        }
        
    except Exception as e:
        print(f"Error generating recommendation: {e}")
        return {"status": "error", "error": str(e)}

def generate_outfit_recommendation_based_on_text(username, input_text):
    """Generate outfit recommendation based on input text"""
    try:
        print(f"Generating recommendation based on text for user {username}")
        
        # Get user's metadata
        metadata_path = get_user_metadata_path(username)
        with open(metadata_path, 'r') as f:
            metadata = json.load(f)
            
        if not metadata:
            return {"status": "error", "error": "No items found"}
        
        # Generate bottom description using LLM
        prompt = f"""Given this user requirement: "{input_text}"
        Suggest a bottom apparel description that matches this requirement.
        Return only a single-line description of the ideal bottom piece."""
        
        chat_completion = client.chat.completions.create(
            model="llama-3.2-90b-text-preview",
            messages=[{"role": "user", "content": prompt}]
        )
        bottom_description = chat_completion.choices[0].message.content.strip()
        print(f"Generated bottom description: {bottom_description}")

        # Convert bottom description to embedding and query BOTTOM collection
        bottom_embedding = fclip.encode_text([bottom_description], batch_size=1)[0]
        normalized_bottom_embedding = bottom_embedding/np.linalg.norm(bottom_embedding)
        
        # Query BOTTOM collection with embedding
        bottoms_collection = get_user_category_collection(username, 'bottom')  # Explicitly query bottoms
        bottom_results = bottoms_collection.query(
            query_embeddings=[normalized_bottom_embedding.tolist()],
            n_results=1,
            include=['metadatas', 'documents']
        )

        if not bottom_results['metadatas'][0]:
            return {"status": "error", "error": "No matching bottom found"}

        best_bottom_metadata = bottom_results['metadatas'][0][0]
        best_bottom = next(
            (item for item in metadata if str(item['image_id']) == str(best_bottom_metadata['image_id'])), 
            None
        )

        if not best_bottom:
            return {"status": "error", "error": "Could not find matching bottom metadata"}

        # Generate top description using LLM
        prompt = f"""Given this user requirement: "{input_text}" and bottom item: "{best_bottom['description']}"
        Suggest a compatible top apparel description that matches this bottom item.
        Return only a single-line description of the ideal top piece."""
        
        chat_completion = client.chat.completions.create(
            model="llama-3.2-90b-text-preview",
            messages=[{"role": "user", "content": prompt}]
        )
        top_description = chat_completion.choices[0].message.content.strip()
        print(f"Generated top description: {top_description}")

        # Convert top description to embedding and query TOP collection
        top_embedding = fclip.encode_text([top_description], batch_size=1)[0]
        normalized_top_embedding = top_embedding/np.linalg.norm(top_embedding)
        
        # Query TOP collection with embedding
        tops_collection = get_user_category_collection(username, 'top')  # Explicitly query tops
        top_results = tops_collection.query(
            query_embeddings=[normalized_top_embedding.tolist()],
            n_results=1,
            include=['metadatas', 'documents']
        )

        if not top_results['metadatas'][0]:
            return {"status": "error", "error": "No matching top found"}

        best_top_metadata = top_results['metadatas'][0][0]
        best_top = next(
            (item for item in metadata if str(item['image_id']) == str(best_top_metadata['image_id'])), 
            None
        )

        if not best_top:
            return {"status": "error", "error": "Could not find matching top metadata"}

        return {
            "status": "success",
            "base_item": {
                "image_url": f"/static/uploads/{username}/{best_bottom['filename']}",
                "description": best_bottom['description'],
                "title": best_bottom['title'],
                "type": best_bottom['apparel_type']
            },
            "recommended_item": {
                "image_url": f"/static/uploads/{username}/{best_top['filename']}",
                "description": best_top['description'],
                "title": best_top['title'],
                "type": best_top['apparel_type']
            }
        }
        
    except Exception as e:
        print(f"Error generating recommendation based on text: {e}")
        return {"status": "error", "error": str(e)}