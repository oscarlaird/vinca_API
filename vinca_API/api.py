from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse
from fastapi import Depends
from sqlite3 import Cursor  # for type checking
from vinca._card import Card
from vinca._cardlist import Cardlist
import typing
import base64
from io import BytesIO

from vinca_API.authentication import get_user_db_cursor

def interrogate(component):
    from fire import Fire
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
    tags: str = None
    last_edit_date: float = None
    last_review_date: float = None
    review_seconds: int = None
    edit_seconds: int = None
    merit: int = None

class API_Review(BaseModel):
    card_id: int
    grade: str

# Reviews and Edits need metadata
class Metadata(BaseModel):
    date: float
    seconds: int

class API_MediaUpload(BaseModel):
    content: str
    base64: bool

class HypotheticalDueDates(BaseModel):
    again: float
    hard: float
    good: float
    easy: float

router = APIRouter()

@router.get('/hypothetical_due_dates', response_model=HypotheticalDueDates)
async def hypothetical_due_dates(card_id: int, date: float, cursor: Cursor = Depends(get_user_db_cursor)):
    c = Card(card_id, cursor)
    if not c:
        raise HTTPException(404, f'Card {card_id} does not exist!')
    dict = c.hypo_due_dates(date = date, relative = False)
    return HypotheticalDueDates(**dict)

@router.post('/review')
async def review_card(review: API_Review, metadata: Metadata, cursor: Cursor = Depends(get_user_db_cursor)):
    ''' Send a review to the server. It is recorded and the card is accordingly scheduled and a new due date is returned.'''
    #assert False, f'{review.card_id}, {review.grade}'
    c = Card(review.card_id, cursor)
    if not c:
        raise HTTPException(404, f'Card {review.card_id} does not exist!')
    c._log(review.grade, seconds=metadata.seconds)

@router.post('/commit_card')
async def commit_card(card: API_Card, metadata: Metadata, cursor: Cursor = Depends(get_user_db_cursor)):
    log(card.id, card.merit)
    assert card.id != 0;
    # get the old card
    old = Card(card.id, cursor)
    # update the old card on (1) editable fields (2) where the new card has a different value
    # the guard (not old or v!=old[k]) says we need to update if the old card doesn't exist (i.e. !old)
    # or if the old card doesn't agree with the new one on this field.
    update_params = {k:v for k,v in dict(card).items() if k in Card._editable_fields and (v is not None) and (not old or v!=old[k])}
    old._update(update_params, date=metadata.date, seconds=metadata.seconds)
    return serialize(old);

@router.post('/upload_media')
async def upload_media(new: API_MediaUpload, cursor: Cursor = Depends(get_user_db_cursor)):
    content = new.content
    if new.base64: # bool indicating whether we need to base64 decode
        content = new.content.split('base64,')[1]    # strip the "png/image:base64," prefix that javascript adds.
        content = base64.standard_b64decode(content) # convert text back to binary
    media_id = Card._upload_media(cursor=cursor, content=content)
    return {'media_id': str(media_id)}

@router.get('/get_media')
async def get_media(media_id: int, cursor: Cursor = Depends(get_user_db_cursor)):
    media = Card._get_media(cursor, media_id)
    if not media:
        raise HTTPException(404, f'Media {media_id} does not exist!')
    return StreamingResponse(BytesIO(media)) if type(media) is bytes else media

@router.get('/get_occlusion_data')
async def get_occlusion_data(media_id: int, cursor: Cursor = Depends(get_user_db_cursor)):
    data = Card._get_media(cursor, media_id)
    if not data:
        raise HTTPException(404, f'Occlusion data @ {media_id} does not exist!')
    return data

def serialize(card: Card):
    # serialize a vinca Card to json
    ''' only real fields, not virtual ones like front-image '''
    fields = {k: card[k] for k in Card._concrete_fields}
    # cast ids to strs because the ids are 64bits but
    # javascript rounds off 64 bit integers to 56 bits.
    for k in Card._id_fields:
        fields[k] = str(fields[k])
    return fields

@router.get('/card')
async def card(id: int, cursor: Cursor = Depends(get_user_db_cursor)):
    c = Card(id, cursor)
    return serialize(c)

#GET /cardlist?deleted=false&search=&due=null&new=null&images=null&audio=null&tag=null&card_type=&created_after=null&created_before=null&due_after=null&due_before=null HTTP/1.1 200 OK

class Filters(BaseModel):
    deleted: typing.Union[bool, None]
    due:     typing.Union[bool, None]
    new:     typing.Union[bool, None]
    images:  typing.Union[bool, None]
    audio:   typing.Union[bool, None]
    search:      typing.Union[str,None]
    tag:         typing.Union[str, None]
    card_type:   typing.Union[str,None]
    created_after:   typing.Union[str, None]
    created_before:  typing.Union[str, None]
    due_after:       typing.Union[str, None]
    due_before:      typing.Union[str, None]

class SortCriterion(BaseModel):
    sort: str

@router.post('/cardlist')
async def _(filters: Filters, crit: SortCriterion, cursor: Cursor = Depends(get_user_db_cursor)):
    filters_copy = dict(filters)
    del filters_copy['due']
    not_due = Cardlist(cursor).sort(crit.sort).filter(**filters_copy, due=False)
    due     = Cardlist(cursor).sort(crit.sort).filter(**filters_copy, due=True)
    if filters.due == True:
        return [serialize(c) for c in due.explicit_cards_list(LIMIT=100)]
    if filters.due == False:
        return [serialize(c) for c in not_due.explicit_cards_list(LIMIT=100)]
    if filters.due == None:
        return  [serialize(c) for c in due.explicit_cards_list(LIMIT=50)] + [serialize(c) for c in not_due.explicit_cards_list(LIMIT=50)]

@router.get('/collection_tags', response_model=typing.List[str])
async def _(cursor: Cursor = Depends(get_user_db_cursor)):
    return Cardlist.all_tags(cursor)

@router.post('/purge')
async def _(filters: Filters, cursor: Cursor = Depends(get_user_db_cursor)):
    Cardlist(cursor).filter(**dict(filters))._purge()

    #filter_params = {key: session[key] for key in default_filter_params}
    #cardlist = cardlist.filter(**filter_params)
    #cardlist = cardlist.sort(session['sort_by'])
    #if session['search']:
        #cardlist = cardlist.findall(session['search'])
    # TODO we set all the filter criteria of the cardlist based on the session filter criteria

def log(*args):
    print(*args,file=open('/home/oscar/log','a'), flush=True)

