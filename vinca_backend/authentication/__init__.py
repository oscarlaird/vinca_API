

passwords = {}
for line in open('passwords.csv').readlines():
   user, password = line.split(',',1)
   passwords[user] = password

@app.get('/register')
def register(user: str, password: str):
    open('passwords.csv','a').write(user + ',' + password + '\n')

@app.post('/token')
def _(form_data: OAuth2PasswordRequestForm=Depends()):
    if form_data.username != 'bad':
        return {"access_token": 'mytoken', "token_type":"bearer"}
    else:
        raise HTTPException(status_code=400, detail="Incorrect username or password")

def fake_decode_token(token: str):
    return token + 'george'

def get_current_user(token: str = Depends(oauth2_scheme)):
    user = fake_decode_token(token)
    return user

@app.get('/debug')
async def debug(number: int, user: str = Depends(get_current_user)):
    return number, user
    # interrogate(request)

