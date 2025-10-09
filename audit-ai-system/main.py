from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from routers import audit, assistant

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

# Include routers
app.include_router(audit.router)
app.include_router(assistant.router)

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
