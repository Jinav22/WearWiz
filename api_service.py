from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import asyncio
from typing import Dict, Optional
import uvicorn
from pydantic import BaseModel
import json
import os
from ai_handler import process_in_background, generate_outfit_recommendation, generate_outfit_recommendation_for_apparel, generate_outfit_recommendation_based_on_text
from concurrent.futures import ThreadPoolExecutor
import logging

# Initialize logging
logging.basicConfig(level=logging.DEBUG)

app = FastAPI()

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global task storage
processing_tasks: Dict[str, asyncio.Task] = {}
executor = ThreadPoolExecutor(max_workers=3)

class ProcessingStatus(BaseModel):
    image_id: str
    status: str
    description: Optional[str] = None
    error: Optional[str] = None

class RecommendationRequest(BaseModel):
    username: str

class ApparelRecommendationRequest(BaseModel):
    username: str
    image_id: str
    description: str
    apparel_type: str

class TextRecommendationRequest(BaseModel):
    username: str
    input_text: str

def get_user_metadata_path(username):
    metadata_dir = 'user_metadata'
    os.makedirs(metadata_dir, exist_ok=True)
    return os.path.join(metadata_dir, f'{username}_metadata.json')

def find_image_metadata(image_id: str):
    """Find image metadata in user-specific files"""
    metadata_dir = 'user_metadata'
    if os.path.exists(metadata_dir):
        for metadata_file in os.listdir(metadata_dir):
            if not metadata_file.endswith('_metadata.json'):
                continue
            
            metadata_path = os.path.join(metadata_dir, metadata_file)
            try:
                with open(metadata_path, 'r') as f:
                    metadata = json.load(f)
                    for item in metadata:
                        if str(item.get('image_id')) == str(image_id):
                            return item, metadata_path
            except (json.JSONDecodeError, FileNotFoundError):
                continue
    return None, None

@app.post("/process-image/{image_id}")
async def process_image(image_id: str, filename: str, image_path: str):
    """Start async processing of an image"""
    logging.debug(f"Received request to process image: {image_id}, filename: {filename}, path: {image_path}")
    try:
        loop = asyncio.get_event_loop()
        task = loop.run_in_executor(
            executor,
            process_in_background,
            image_id,
            filename,
            image_path
        )
        
        processing_tasks[image_id] = task
        return {"status": "processing", "image_id": image_id}
    except Exception as e:
        logging.error(f"Error processing image {image_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/processing-status/{image_id}")
async def get_processing_status(image_id: str):
    """Check the processing status of an image"""
    try:
        if image_id not in processing_tasks:
            item, _ = find_image_metadata(image_id)
            if item:
                processing_status = item.get('processing_status', 'completed')
                if processing_status == 'completed':
                    return {"status": "completed"}
                elif processing_status == 'error':
                    return {"status": "error"}
            return {"status": "not_found"}
        
        task = processing_tasks[image_id]
        if task.done():
            del processing_tasks[image_id]
            try:
                result = task.result()
                return {"status": "completed" if result else "error"}
            except Exception as e:
                return {"status": "error", "error": str(e)}
        
        return {"status": "processing"}
    except Exception as e:
        return {"status": "error", "error": str(e)}

@app.post("/generate-recommendation")
async def generate_recommendation(request: RecommendationRequest):
    """Generate random outfit recommendation"""
    logging.debug(f"Received request for random recommendation: {request}")
    try:
        loop = asyncio.get_event_loop()
        task = loop.run_in_executor(
            executor,
            generate_outfit_recommendation,
            request.username
        )
        
        result = await task
        return result
    except Exception as e:
        logging.error(f"Error generating recommendation: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/generate-recommendation-for-apparel")
async def generate_recommendation_for_apparel(request: ApparelRecommendationRequest):
    """Generate outfit recommendation based on specific apparel"""
    logging.debug(f"Received request for apparel recommendation: {request}")
    try:
        loop = asyncio.get_event_loop()
        task = loop.run_in_executor(
            executor,
            generate_outfit_recommendation_for_apparel,
            request.username,
            request.image_id,
            request.description,
            request.apparel_type
        )
        result = await task
        return result
    except Exception as e:
        logging.error(f"Error generating recommendation for apparel: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/generate-recommendation-based-on-text")
async def generate_recommendation_based_on_text(request: TextRecommendationRequest):
    """Generate outfit recommendation based on input text"""
    logging.debug(f"Received request for text-based recommendation: {request}")
    try:
        loop = asyncio.get_event_loop()
        task = loop.run_in_executor(
            executor,
            generate_outfit_recommendation_based_on_text,
            request.username,
            request.input_text
        )
        result = await task
        return result
    except Exception as e:
        logging.error(f"Error generating recommendation based on text: {e}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)