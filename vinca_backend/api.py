from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse
from fastapi import Depends
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")
import sqlite3
from vinca._card import Card
from vinca._cardlist import Cardlist
import typing
from fire import Fire
import base64
from io import BytesIO

def interrogate(component):
    Fire(component=component, command=['--','--interactive'])

from pydantic import BaseModel

class API_Card(BaseModel):
    id: int = None
    front_text: str = None
    back_text: str = None
    card_type: str = None
    visibility: str = None
    create_date: float = None
    due_date: float = None
    front_image_id: int = None
    back_image_id: int = None
    front_audio_id: int = None
    back_audio_id: int = None
    tags: typing.List[str] = []

class API_Review(BaseModel):
    card_id: int
    grade: str

# Reviews and Edits need metadata
class Metadata(BaseModel):
    date: float
    seconds: int

class API_MediaUpload(BaseModel):
    name: str
    content: str

router = APIRouter()

@router.get('/hypothetical_due_dates')
async def _(card_id: int, date: float):
    c = get_card(card_id)
    if not c:
        raise HTTPException(404, f'Card {card_id} does not exist!')
    return c.hypo_due_dates(date = date, relative = False)

@router.post('/review')
async def review_card(review: API_Review, metadata: Metadata):
    ''' Send a review to the server. It is recorded and the card is accordingly scheduled and a new due date is returned.'''
    log(review.card_id, review.grade)
    #assert False, f'{review.card_id}, {review.grade}'
    c = get_card(review.card_id)
    if not c:
        raise HTTPException(404, f'Card {review.card_id} does not exist!')
    c._log(review.grade, seconds=10)
    new_due_date = c._schedule()
    return {'new_due_date': new_due_date}


@router.post('/commit_card')
async def commit_card(card: API_Card, metadata: Metadata):
    log(card.front_image_id, card.back_image_id)
    # get the old card, or create one if it doesn't exist
    old = get_card(card.id) or Card._new_card(get_db_cursor())
    # update the old card on (1) editable fields (2) where the new card has a different value
    update_params = {k:v for k,v in dict(card).items() if k in Card._editable_fields and v!=old[k]}
    old._update(update_params)
    # update tags
    old.edit_tags(new_tags = card.tags)
    return serialize(old);

@router.post('/upload_media')
async def upload_media(new: API_MediaUpload):
    cursor = get_db_cursor();
    content = new.content.split('base64,')[1] # convert text back to binary
    content = base64.standard_b64decode(content)
    name = new.name.split('.')[0]  # remove file extension from filename
    media_id = Card._upload_media(cursor=cursor, content=content, name=name)
    return {'media_id': str(media_id)}

@router.get('/get_media')
async def get_media(media_id: int):
    media = Card._get_media(get_db_cursor(), media_id)
    if not media:
        raise HTTPException(404, f'Media {media_id} does not exist!')
    log(type(media))
    return StreamingResponse(BytesIO(media))

def serialize(card: Card):
    # serialize a vinca Card to json
    ''' only real fields, not virtual ones like front-image '''
    fields = {k: card[k] for k in Card._concrete_fields}
    # cast ids to strs because the ids are 64bits but
    # javascript rounds off 64 bit integers to 56 bits.
    for k in Card._id_fields:
        fields[k] = str(fields[k])
    fields['tags'] = card.tags
    return fields

@router.get('/card')
async def card(id: int):
    c = get_card(id)
    return serialize(c)

@router.get('/cardlist')
async def _():
    cl = get_cardlist()
    collection_tags = cl.all_tags
    return {'cards': [serialize(c) for c in cl],
            'collection_tags': collection_tags}

def get_db_cursor():
    return sqlite3.connect('/home/oscar/learning.db').cursor()

def get_card(id):
    return Card(id, get_db_cursor())
def get_cardlist():
    return Cardlist(get_db_cursor())
    #filter_params = {key: session[key] for key in default_filter_params}
    #cardlist = cardlist.filter(**filter_params)
    #cardlist = cardlist.sort(session['sort_by'])
    #if session['search']:
        #cardlist = cardlist.findall(session['search'])
    # TODO we set all the filter criteria of the cardlist based on the session filter criteria

def log(*args):
    print(*args,file=open('/home/oscar/log','a'), flush=True)

