import motor.motor_asyncio
from bson import ObjectId
from io import BytesIO
from . import database
from .stasilogging import *
import time

# Create a new instance of the MotorClient and get the database
client = database.client
db = client.gridfs # replace 'mydatabase' with your database name
fs = motor.motor_asyncio.AsyncIOMotorGridFSBucket(db)

async def update_file(filename, bytes_io, **kwargs):
    t = time.time()
    log("gridfs", "update_file", f"Updating file {filename}", False)
    # Generate a random ObjectId as fileid
    fileid = ObjectId()
    # Upload the file to GridFS
    await fs.upload_from_stream_with_id(fileid, filename, bytes_io, metadata=kwargs)
    log("gridfs", "update_file", f"Updated file {filename} ({fileid}) in {round(time.time() - t, 5)} seconds", False)
    return str(fileid)

async def update_file_by_id(id, filename, bytes_io, **kwargs):
    # Upload the file to GridFS, using the given id, update if exists, insert if not
    t = time.time()
    log("gridfs", "update_file_by_id", f"Updating file {id} with {filename}", False)
    await fs.upload_from_stream_with_id(id, filename, bytes_io, metadata=kwargs)
    log("gridfs", "update_file_by_id", f"Updated file {id} with {filename} in {round(time.time() - t, 5)} seconds", False)
    return str(id)

async def delete_file(id):
    try:
        # Delete the file from GridFS
        d = await fs.delete(ObjectId(id))
        log("gridfs", "delete_file", f"Deleted file {id}", False)
        return True
    except motor.motor_asyncio.gridfs.NoFile:
        log("gridfs", "delete_file_404", f"Tried to delete {id} but wasn't found", False)
        
        return False

async def get_file(id):
    t = time.time()
    log("gridfs", "get_file", f"Getting file {id}", False)
    try:
        # Get the file from GridFS
        grid_out = await fs.open_download_stream(ObjectId(id))
        bytes_io = BytesIO()
        bytes_io.write(await grid_out.read())
        bytes_io.seek(0)
        log("gridfs", "get_file", f"Got file {id} in {round(time.time() - t, 5)} seconds")
        return {
            "file": bytes_io,
            "filename": grid_out.filename,
            **grid_out.metadata
        }
    except motor.motor_asyncio.gridfs.NoFile:
        log("gridfs", "get_file_404", f"Tried to get {id} but wasn't found", False)
        return None