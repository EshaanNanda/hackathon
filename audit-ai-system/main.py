from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from routers import audit, assistant
from routers import agents


app = FastAPI(
    title="AutonomIQ Audit AI System",
    description="AI-powered audit management system with RAG capabilities",
    version="1.0.0"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve main HTML file
@app.get("/")
async def serve_frontend():
    """Serve the main HTML file"""
    return FileResponse("main1.html")

@app.get("/main1.html")
async def serve_frontend_alt():
    """Alternative route for main1.html"""
    return FileResponse("main1.html")

# Include routers
app.include_router(audit.router)
app.include_router(assistant.router)
app.include_router(agents.router)

@app.get("/")
async def root():
    return {
        "message": "AutonomIQ Audit AI System API",
        "version": "1.0.0",
        "status": "running"
    }

@app.get("/health")
async def health_check():
    return {"status": "healthy"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
