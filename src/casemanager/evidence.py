from .. import gridfs, utils
import datetime
import discord
from typing import *

class Seal:

    def __init__(self):
        self.id = None
        self.desc = None
        self.created = None
        self.author = None
    
    def fromDict(self, data):
        self.id = data["id"]
        self.desc = data["desc"]
        self.created = data["created"].replace(tzinfo=datetime.timezone.utc)
        self.author = data["author"]
        return self

    def New(self, desc, author_id: int):
        if isinstance(author_id, discord.Member):
            author_id = author_id.id
        self.id = utils.randomKey(4)
        self.desc = desc
        self.created = datetime.datetime.now(datetime.timezone.utc)
        self.author = author_id
        return self

class Evidence:
    
    def __init__(self, id: str = None):
        self.filename = None
        self.kwargs = None
        self.file_id = None
        self.id = id
        self.created = None
        self.certified = False
        self.seals: List[Seal] = []  # key -> desc

    def fromDict(self, data):
        self.filename = data["filename"]
        self.file_id = data["file_id"]
        self.author = data["author"]
        self.id = data["id"]
        self.seals = [Seal().fromDict(seal) for seal in data["seals"]]
        self.created = data["created"].replace(tzinfo=datetime.timezone.utc)
        self.certified = data["certified"]
        return self
    
    def toDict(self):
        return {
            "filename": self.filename,
            "file_id": self.file_id,
            "author": self.author,
            "id": self.id,
            "seals": [seal.toDict() for seal in self.sealed],
            "created": self.created,
            "certified": self.certified
        }
    
    def addSeal(self, desc, author_id: int):
        if isinstance(author_id, discord.Member):
            author_id = author_id.id
        new_seal = Seal().New(desc, author_id)
        self.seals.append(new_seal)
        return new_seal
    
    def delSeal(self, seal_id: str):
        old_len = len(self.seals)
        self.seals = [seal for seal in self.seals if seal.id != seal_id]
        return old_len == len(self.seals)  # if true, seal was deleted
        
    def isSealed(self):
        return len(self.seals) > 0

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

