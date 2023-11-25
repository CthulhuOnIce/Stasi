import motor.motor_asyncio
from bson import ObjectId
from io import BytesIO
from . import database
from .stasilogging import *

# Create a new instance of the MotorClient and get the database
client = database.client
db = client.gridfs # replace 'mydatabase' with your database name
fs = motor.motor_asyncio.AsyncIOMotorGridFSBucket(db)

async def update_file(filename, bytes_io, **kwargs):
    # Generate a random ObjectId as fileid
    fileid = ObjectId()
    # Upload the file to GridFS
    await fs.upload_from_stream_with_id(fileid, filename, bytes_io, metadata=kwargs)
    return str(fileid)

async def update_file_by_id(id, filename, bytes_io, **kwargs):
    # Upload the file to GridFS, using the given id, update if exists, insert if not
    await fs.upload_from_stream_with_id(id, filename, bytes_io, metadata=kwargs)
    return str(id)

async def delete_file(id):
    try:
        # Delete the file from GridFS
        d = await fs.delete(ObjectId(id))
        log("gridfs", "delete_file", f"Deleted file {id} ({d})")
        return True
    except motor.motor_asyncio.gridfs.NoFile:
        log("gridfs", "delete_file_404", f"Tried to delete {id} but wasn't found")
        
        return False

async def get_file(id):
    try:
        # Get the file from GridFS
        grid_out = await fs.open_download_stream(ObjectId(id))
        bytes_io = BytesIO()
        bytes_io.write(await grid_out.read())
        bytes_io.seek(0)
        return {
            "file": bytes_io,
            "filename": grid_out.filename,
            **grid_out.metadata
        }
    except motor.motor_asyncio.gridfs.NoFile:
        return None