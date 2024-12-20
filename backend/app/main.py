# main.py
import os
from typing import List, Optional
from fastapi import FastAPI, HTTPException, Depends
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from pydantic import BaseModel
import pandas as pd
from dotenv import load_dotenv

# EmbeddingRecommender class and other necessary components
from app.recommender import EmbeddingRecommender, AsyncOpenAIClient, CosineSimilarityCalculator

# Load environment variables from the project root
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(__file__)), '.env'))

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Initialize the recommender
    get_recommender()
    yield
    # Shutdown: Clean up resources if needed
    # This runs when the application is shutting down
    pass

# Initialize FastAPI app
app = FastAPI(title="Course Recommender API", lifespan=lifespan)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, replace with frontend domain
    allow_credentials=True,
    allow_methods=["*"],  # Allows all methods
    allow_headers=["*"],  # Allows all headers
)

# Pydantic models for request
class RecommendationRequest(BaseModel):
    query: str
    levels: Optional[List[int]] = None

# Global variable to store the EmbeddingRecommender instance
recommender = None

def get_recommender():
    """
    Creates and returns an instance of EmbeddingRecommender.
    This function is used as a dependency, ensuring we only create one instance.
    """
    global recommender
    if recommender is None:
        # Load the course data from pkl
        pkl_path = "embeddings.pkl"
        df = pd.read_pickle(pkl_path)
        
        # Initialize the AsyncOpenAIClient
        config = {
            "OPENAI_API_KEY": os.getenv("OPENAI_API_KEY"),
            "OPENAI_API_VERSION": os.getenv("OPENAI_API_VERSION"),
            "OPENAI_API_BASE": os.getenv("OPENAI_API_BASE"),
            "OPENAI_ORGANIZATION_ID": os.getenv("OPENAI_ORGANIZATION_ID"),
            "GENERATOR_MODEL": os.getenv("GENERATOR_MODEL"),
            "RECOMMENDER_MODEL": os.getenv("RECOMMENDER_MODEL"),
            "OPENAI_EMBEDDING_MODEL": os.getenv("OPENAI_EMBEDDING_MODEL")
        }
        openai_client = AsyncOpenAIClient(config)
        
        # Initialize the CosineSimilarityCalculator
        similarity_calculator = CosineSimilarityCalculator()
        
        # Initialize the EmbeddingRecommender
        recommender = EmbeddingRecommender(openai_client, similarity_calculator)
        recommender.load_courses(df.to_dict('records'))
    return recommender

@app.get("/")
async def root():
    """
    Root endpoint to check if the API is running.
    """
    return {"message": "Course Recommender API is running"}

# @app.post("/recommend")
# async def recommend_courses(
#     request: RecommendationRequest,
#     recommender: EmbeddingRecommender = Depends(get_recommender)
# ):
#     """
#     Endpoint to get course recommendations based on user query and preferred levels.
#     Returns a streaming response of OpenAI tokens.

#     Args:
#     - request (RecommendationRequest): Contains the user's query and preferred course levels.
#     - recommender (EmbeddingRecommender): Instance of the recommender, injected as a dependency.

#     Returns:
#     - StreamingResponse: A stream of tokens from the OpenAI API.
#     """
#     return StreamingResponse(
#         recommender.stream_recommend(levels=request.levels, query=request.query),
#         media_type="text/plain"
#     )

@app.post("/recommend")
async def recommend_courses(
    request: RecommendationRequest,
    recommender: EmbeddingRecommender = Depends(get_recommender)
):
    """
    Endpoint to get course recommendations based on user query and preferred levels.
    Returns a string response of recommendations.

    Args:
    - request (RecommendationRequest): Contains the user's query and preferred course levels.
    - recommender (EmbeddingRecommender): Instance of the recommender, injected as a dependency.

    Returns:
    - str: A string containing the course recommendations.
    """
    recommendation = await recommender.recommend(query=request.query, levels=request.levels)
    return recommendation

@app.get("/health")
async def health_check():
    """
    Health check endpoint to verify if the service and its dependencies are functioning correctly.
    """
    try:
        # Perform a simple operation to check if the recommender is working
        recommender = get_recommender()
        test_query = "test query"
        async for _ in recommender.stream_recommend(query=test_query, levels=[]):
            break
        return {"status": "healthy"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Service unhealthy: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)