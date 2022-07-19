from fastapi import APIRouter, Depends, Request, UploadFile
from fastapi.responses import StreamingResponse
from sqlite3 import Cursor # for type checking
import shutil
from tempfile import NamedTemporaryFile
from pathlib import Path
from io import BytesIO
messenger_template = Path(__file__).parent / 'messenger.sqlite'

from vinca_API.authentication import get_user_db_cursor

router = APIRouter()

@router.get('/test')
def _():
    return 10
    return {'a': 1}

@router.post('/client_changes')
async def client_changes(file: UploadFile, cursor: Cursor = Depends(get_user_db_cursor)):
    # 1 save received data into database called client_messenger
    # 2 copy over records which we do not already have
    # 3 send back the timestamps of added records in a database called server_messenger
    with NamedTemporaryFile() as client_messenger, NamedTemporaryFile() as server_messenger:
        # 1 save received data into database called client_messenger
        content = file.file.read() # binary contents of the database
        client_messenger.write(content)
        cursor.execute(f'ATTACH DATABASE "{client_messenger.name}" AS CM')
        # 2 copy over records which we do not already have
        for table in ('edits','reviews','media'):
            # We simply copy in all records because
            # Our database is configured to ignore records with already existing id
            cursor.execute(f'INSERT INTO {table} SELECT * FROM CM.{table}')
        # 3 send back the timestamps of added records in a database called server_messenger
        shutil.copy(messenger_template, server_messenger.name)
        cursor.execute(f'ATTACH DATABASE "{server_messenger.name}" AS SM')
        for table in ('edits','reviews','media'):
            cursor.execute(f'INSERT INTO SM.{table} (id, server_timestamp) \
                            SELECT t.id, t.server_timestamp FROM {table} AS t \
                            INNER JOIN CM.{table} ON t.id = CM.{table}.id')
        cursor.connection.commit()
        cursor.connection.close()
        content = BytesIO(server_messenger.read())
        return StreamingResponse(content)

@router.get('/server_changes')
async def server_changes(latest_timestamp: int = 0, cursor: Cursor = Depends(get_user_db_cursor)):
    # 0 The client tells us the latest_timestamp they possess
    # 1 Select all records with a later timestamp into a messenger db
    with NamedTemporaryFile() as messenger:
        shutil.copy(messenger_template, messenger.name)
        cursor.execute(f'ATTACH DATABASE "{messenger.name}" AS messenger')
        for table in ('edits','reviews','media'):
            cursor.execute(f'INSERT INTO messenger.{table} SELECT * FROM {table} \
                             WHERE server_timestamp > {latest_timestamp}')
        cursor.connection.commit()
        cursor.connection.close()
        content = BytesIO(messenger.read())
        return StreamingResponse(content)

# -----------------------------------------------------------------------------

# From the Client Side interaction looks like this:

# 0. Authenticate
#    The client types their password in on the command line and sends it to server
#    They get back an authentication token which will be included in the header of 
#    Their subsequent requests
# 1. Post
#    The client copies all records from media, edits, and reviews where timestamp is null into another table
#    They send this table in the body of a POST request
#    The server then copies all of these records into itself and this triggers timestamping
#    (it only copies those records which it doesn't have yet)
#    The server replies with all of those records just added
# 2. Get
#    Assert that every single record clientside has a timestamp
#    The client finds the maximum timestamp in its database
#    It asks for all of the records with a later timestamp.
#    The server selects all those records with a later timestamp into a table
#    It replies with this table file which is guaranteed to be disjoint with the client's database
#    The client can safely insert all records into itself.
#    The client is up-to-date.
#(3. Class Syncing)
#    Rich statistics are run on each student
#    These are reported en-masse to the teacher
#    Students can be checked-out individually
