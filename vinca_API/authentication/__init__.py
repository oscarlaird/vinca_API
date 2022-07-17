from fastapi import Depends, APIRouter, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")
from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import BaseModel
from pathlib import Path
import sqlite3
import shutil

from vinca_API.authentication.secret_key import SECRET_KEY

router = APIRouter()

template_db = '/home/oscar/modern_cards.db'


# to get a string like this run:
# openssl rand -hex 32
ALGORITHM = "HS256"
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


class Token(BaseModel):
    access_token: str
    token_type: str

class Credentials(BaseModel):
    username: str
    password: str

# passwords database
passwords = {}
passwords_file = Path(__file__).parent / 'passwords.csv'
passwords = dict([line.split(',',1) for line in passwords_file.read_text().splitlines()])

# methods to register a new username + password
@router.post('/register', response_model=Token)
def register(credentials: Credentials):
    u, p = credentials.username, credentials.password
    p = get_password_hash(p)
    log(p)
    passwords_file.open('a').write(u + ',' + p + '\n')
    passwords[u] = p  # update the db
    access_token = create_access_token(
        data={"sub": u},
    )
    return {"access_token": access_token, "token_type": "bearer"}


@router.get('/users_list')
def _():
    return [u for u in passwords]


def get_password_hash(password):
    return pwd_context.hash(password)


# Methods to authenticate a username+password login and return a temporary token
def authenticate_user(username: str, password: str):
    return verify_password(password, passwords.get(username)) and username

def verify_password(plain_password, hashed_password):
    # we can't do a simple hash(plain)===hashed_pass check because
    # the password is salted and the hashed_password contains its own salt
    return pwd_context.verify(plain_password, hashed_password)

# methods to generate and return a token
def create_access_token(data: dict):
    to_encode = data.copy()
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

@router.post("/token", response_model=Token)
async def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends()):
    user = authenticate_user(form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token = create_access_token(
        data={"sub": user}, 
    )
    return {"access_token": access_token, "token_type": "bearer"}

# Methods to authenticate an existing token and return the associated user or database
async def get_current_user(token: str = Depends(oauth2_scheme)):
    if token.startswith('guest'):
        return token
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
            # return 'guest'
    except JWTError:
        raise credentials_exception
        # return 'guest'
    if not username in passwords:
        raise credentials_exception
        # return 'guest'
    return username

async def get_user_db_cursor(user: str = Depends(get_current_user)):
    path = Path(__file__).parent.parent  # directory of vinca-backend module
    path /= 'decks'
    path /= (user + '.sqlite')
    if not path.exists():
        shutil.copy(template_db, path)
    return sqlite3.connect(path).cursor()


def log(*args):
        print(*args,file=open('/home/oscar/log','a'), flush=True)


