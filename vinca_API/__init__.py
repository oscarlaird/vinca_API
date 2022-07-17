from vinca_API import api
from vinca_API import sync
from vinca_API import authentication

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
app.include_router(authentication.router, prefix='/auth')
app.include_router(sync.router, prefix="/sync" )

# if __name__ == "__main__":
    # uvicorn.run(app, host="127.0.0.1", port=8000)
