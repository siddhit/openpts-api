from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(
    title="OpenPTS API",
    description="Open Predetermined Time Standards - REST API for industrial time study calculations",
    version="0.1.0"
)

#Allow frontend to call this API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def read_root():
    return {
        "message":"Welcome to OpenPTS API",
        "docs_url":"/docs",
        "version":"0.1.0"
    }

@app.get("/health")
def health_check():
    return {"status":"healthy"}