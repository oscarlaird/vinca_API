from vinca_backend import api
#from vinca_backend import sync_api

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=[ "http://localhost:8080", ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api.router)

# if __name__ == "__main__":
    # uvicorn.run(app, host="127.0.0.1", port=8000)
