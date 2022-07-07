import sqlite3

from flask import render_template, request, redirect, flash, make_response
from vincaserver import vincaserver as app
app.config.from_mapping(SECRET_KEY='dev',)
import subprocess
from pathlib import Path
import shutil
dbs_path = Path('/home/oscar/web/vincaserver/users/')
tutorial_db = Path('/home/oscar/web/vincaserver/tutorial.db')

def log(*args):
    print(*args,file=open('/home/oscar/log','a'), flush=True)

@app.route('/home/user')
def home(user):
    db_path = dbs_path / user
    c = sqlite3.connect(db_path)
    c.execute('SELECT * FROM cards LIMIT 10')
    return '<br>'.join([str(r) for r in c.fetchall()])

@app.route('/new_user', methods=['GET'])
def new_user():
    ''' create a new user with the tutorial deck '''
    if request.method != 'GET':
        return 'API: /new parameters user'
    user = request.args.get('user')
    db_path = dbs_path / user
    assert not db_path.exists() # we should never overwrite
    shutil.copy(tutorial_db, db_path)
    # TODO set the create dates to today
    # so that these cards schedule normally
    return f'successfully created user {user}'

@app.route('/upload', methods=['POST'])
def upload():
    user = request.args.get('user')
    # TODO this could overwrite
    db_path = dbs_path / user
    c = sqlite3.connect(db_path).cursor()
    # don't upload unless the existing db is empty
    size = c.execute('SELECT count(*) FROM cards').fetchone()[0]; c.close()
    if size > 0:
        return make_response('upload is only allowed once all cards have been '
                             'deleted from the server', 403)
    if request.method == 'POST':
        received_file = request.files['file']
        received_file.save(db_path)
        return make_response('db uploaded',200)
        # TODO change the schema to do autoincrement primary key
        # set server_received_times

@app.route('/clone', methods=['GET'])
def clone():
    user = request.args.get('user')
    if not user:
        return make_response('specify a user',400)
    db_path = dbs_path / user
    if not db_path.exists():
        return make_response(f'user {user} not found',400)
    if request.method == 'GET':
        return db_path.read_bytes()
        # TODO change the schema to remove server_received_times int primary key

@app.route('/client_changes', methods=['POST'])
def client_changes():
    db_path = dbs_path / user
    tmp_path = dbs_path / ('tmp_' + user)
    if request.method == 'POST':
        file = request.files['file']
        # maybe I should load it in memory if it is small which it almost always is
        file.save(tmp_path)
        c = sqlite3.connect(db_path).cursor()
        max_time = c.execute('SELECT max(server_received_time) FROM server_received_times')
        c.execute('attach database ? as changes;',(tmp_path,))
        # add tag_edits etc.
        # if we already had these records, these tables
        # simply IGNORE the insert
        c.execute('insert into tag_edits select * from changes.tag_edits;')
        c.execute('insert into reviews   select * from changes.reviews  ;')
        c.execute('insert into edits     select * from changes.edits    ;')
        c.execute('insert into media     select * from changes.media    ;')
        # in the meantime our server_received_times table has been
        # associating times to each of these records via the triggers
        # so now we reply with the server_received_times table only
        # first detach the received data
        c.execute('detach ?;',(tmp_path,))
        # delete received data
        tmp_path.unlink()
        # now we use the tmp file to store the server_received_time
        c.execute('attach database ? as reply;',(tmp_path,))
        # get schema of server_received_times and copy it to reply
        schema = c.execute("SELECT sql FROM sqlite_master WHERE type='table' AND "
                           "name='server_received_times'").fetchone()[0]
        schema = schema.replace('server_received_times','reply.server_received_times')
        c.execute(schema)
        # copy the relavant data into the reply
        # only send those records which have been added in this function call
        c.execute('INSERT INTO reply.server_received_times SELECT * from '
                  'server_received_times WHERE server_received_time > ?',(max_time,))
        c.connection.commit()
        c.connection.close()
        return tmp_path.read_bytes()

@app.route('/server_changes', methods=['GET'])
def server_changes():
    # the client asks the server for new records
    # we need to send all the records after such and such a date
    if method != 'GET':
        return make_response('api parameters: user last_sync', 400)
    db_path = dbs_path / user
    tmp_path = dbs_path / ('tmp_' + user)
    # copy the schema
    if request.method == 'GET':
        subprocess.run(['sqlite3',db_path,'.schema','|','sqlite3',tmp_path])
        c = sqlite3.connection(tmp_path).cursor()
        c.execute('PRAGMA foreign_keys = OFF')
        # drop uneeded tables
        c.execute('DROP TABLE settings;')
        c.execute('DROP TABLE cards;')
        c.execute('DROP TABLE tags;')
        # copy
        c.execute('ATTACH DATABASE ? AS source;',(db_path,))
        c.execute('INSERT INTO server_received_times SELECT * FROM '
                  'source.server_received_times WHERE source.server_received_time '
                  '> ?',(last_sync,))
        # copy over records which are after the sync_date
        c.execute('INSERT INTO media SELECT source.media.* FROM source.media JOIN '
                  'server_received_times WHERE source.media.id = server_received_times.id')
        c.execute('INSERT INTO edits SELECT source.edits.* FROM source.edits JOIN '
                  'server_received_times WHERE source.edits.id = server_received_times.id')
        c.execute('INSERT INTO tag_edits SELECT source.tag_edits.* FROM source.tag_edits JOIN '
                  'server_received_times WHERE source.tag_edits.id = server_received_times.id')
        c.execute('INSERT INTO reviews SELECT source.reviews.* FROM source.reviews JOIN '
                  'server_received_times WHERE source.reviews.id = server_received_times.id')
        # close
        c.connection.commit()
        c.connection.close()
        # send the data
        return tmp_path.read_bytes()



# From the Client side normal interaction looks like (1) POST (2) GET
# (1) POST
# query all the ids in server_received_times that are null
# these refer to reviews, media, tag_edits, and edits that were created
# locally and have not yet been received by the server
# use these to create reviews, media, tag_edits, and edits subtables
# (I DONT need to create the other four tables in my schema)
# copy these into a separate sqlite database
#! post this over the web to the server which is listening for this
# the client doesn't need to wait for a response, it just hopes it works
# now the server has possibly already received some of these records
# so after attaching to the master and the received databases
# it checks against server_received_times to find out which ones it doesn't have yet
# then it copies these new records into the four appropriate databases
# the triggers go off and keep everything else up to date
# (although in fact there is not any necessary reason that the server needs cards, tags, etc.)
# (but it could be useful because we don't want the web client to have to rebuild the database
#  step by step)
# the triggers will update server_received_times
# (in fact this could just be an integer primary key because this will autoincrement)
# reply with the server_received_times table so that the client will know they
# have been added to the server
# (2) GET
# the client asks the server for new records after the last server_received_time
# the server looks up all the ids which have a later server_received_time
# the process of the server assembling the data to send and transmitting it to the
# client is the same as what we previously saw.
# the only difference is that the client receives server_received_times attached to
# every id.
# everything the client owns should now have a server_received_time; we are done.

# (3) class syncing
# Should all the individuals be attached in database?
# No, the cards will have the same ids because they come
# from the same edits
# This will be fine because a typical deck might be
# 5MB per student so it will work fine in the browser for a typical class,
# but for something bigger it might be necessary to use a desktop
