
import os
import random
import requests
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

# Load environment variables from a .env file
load_dotenv()

app = FastAPI()

# --- CORS Middleware ---
# This is crucial to allow your HTML frontend to communicate with this backend.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins
    allow_credentials=True,
    allow_methods=["*"],  # Allows all methods (GET, POST, etc.)
    allow_headers=["*"],  # Allows all headers
)

# --- Pydantic Model ---
# This defines the expected structure of the request body for our endpoint.
class Requirement(BaseModel):
    text: str

# --- Tavily API Function ---
def search_tavily(query: str):
    """
    Searches Tavily for a given query and returns the results.
    """
    api_key = os.getenv("TAVILY_API_KEY")
    if not api_key:
        print("ERROR: TAVILY_API_KEY environment variable not set.")
        raise HTTPException(status_code=500, detail="Tavily API key is not configured on the server.")

    try:
        response = requests.post(
            "https://api.tavily.com/search",
            json={
                "api_key": api_key,
                "query": query,
                "search_depth": "basic",
                "include_answer": False,
                "max_results": 5 # We'll fetch 5 vendors for this demo
            },
        )
        response.raise_for_status()  # Raise an exception for bad status codes
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"ERROR: Could not connect to Tavily API. {e}")
        raise HTTPException(status_code=503, detail="Could not connect to the vendor search service.")


# --- API Endpoint ---
@app.post("/search-vendors")
def search_vendors_endpoint(requirement: Requirement):
    """
    Receives a requirement, searches for vendors using Tavily,
    and returns a structured list of vendors with placeholder data.
    """
    print(f"Received requirement: {requirement.text}")

    # Create a more specific search query for better results
    search_query = f"Top-rated audio, visual, and event vendors for: '{requirement.text}'"
    print(f"Searching Tavily with query: {search_query}")

    tavily_results = search_tavily(search_query)

    vendors = []
    if "results" in tavily_results:
        for i, result in enumerate(tavily_results["results"]):
            # --- Data Transformation ---
            # Here we adapt the raw search result to the structure the frontend expects.
            # We generate realistic placeholder data for fields not provided by the search API.
            vendors.append({
                "id": f"v-api-{i+1}",
                "name": result.get("title", "Unnamed Vendor"),
                "tags": random.sample(['audio', 'events', 'lighting', 'it', 'decor'], k=random.randint(1, 3)),
                "revenue": random.randint(500000, 3000000),
                "profile": random.randint(75, 95),
                "rating": round(random.uniform(4.0, 5.0), 1),
                "reviews": [
                    {"rating": round(random.uniform(4.0, 5.0), 1), "comment": result.get("content", "No description available.")},
                    {"rating": round(random.uniform(4.0, 5.0), 1), "comment": "Provided excellent service for our event."}
                ]
            })

    print(f"Returning {len(vendors)} vendors to frontend.")
    return vendors