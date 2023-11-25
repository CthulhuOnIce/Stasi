from . import gridfs
import datetime
import discord

class Evidence:
    
    def __init__(self, id: str = None):
        self.filename = None
        self.kwargs = None
        self.file_id = None
        self.id = id
        self.created = None

    def fromDict(self, data):
        self.filename = data["filename"]
        self.file_id = data["file_id"]
        self.author = data["author"]
        self.id = data["id"]
        self.created = data["created"]
        return self

    async def New(self, filename, bytes_io, author_id: int):
        if isinstance(author_id, discord.Member):
            author_id = author_id.id
            
        self.filename = filename
        self.created = datetime.datetime.now(datetime.timezone.utc)
        self.author = author_id
        self.file_id = await gridfs.update_file(filename, bytes_io, created=self.created)
        return self

    async def update(self, filename, bytes_io):
        self.filename = filename
        self.bytes_io = bytes_io
        await self.save()

    async def delete(self):
        await gridfs.delete_file(self.file_id)

    async def save(self):
        await gridfs.update_file_by_id(self.file_id, self.filename, self.bytes_io, created=self.created)

    async def getFile(self):
        return await gridfs.get_file(self.file_id)

    async def getRawFile(self):
        file = await self.getFile()
        return file["filename"], file["file"] 

