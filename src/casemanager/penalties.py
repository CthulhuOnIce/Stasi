from __future__ import annotations

from typing import *

if TYPE_CHECKING:
    from .casemanager import Case

from .. import utils, warden
from ..stasilogging import *


class Penalty:
    def __init__(self, case):
        self.case: Case = case
        return

    def __str__(self):
        return self.describe()

    def __repr__(self):
        return self.describe()

    def describe(self):
        return "Blank Penalty"
    
    def toDict(self):
        s = self.__dict__
        s["type"] = self.__class__.__name__
        if "case" in s:
            del s["case"]
        return s

    def load(self):
        return
    
    async def Execute(self):
        return

class WarningPenalty(Penalty):
    def __init__(self, case):
        super().__init__(case)
        self.warning_text = None
        return
    
    def New(self, warning_text: str):
        self.warning_text = warning_text
        return self

    def describe(self):
        return f"Warning: {self.warning_text}"

    # needs to be made async for implementation
    async def Execute(self):
        # note = await db.add_note(self.case.defense.id, self.case.plaintiff.id, f"User Warned as Penalty of Case {self.case.id}: `{self.warning_text}`")
        print(f"User Warned as Penalty of Case {self.case.id}: `{self.warning_text}`")
    
class PermanentBanPenalty(Penalty):
    def __init__(self, case):
        super().__init__(case)
        self.ban_text = None
        return
    
    def New(self, ban_text: str):
        self.ban_text = ban_text
        return self
    
    def describe(self):
        return f"Permanent Ban: {self.ban_text}"
    
    async def Execute(self):
        # await self.case.guild.ban(self.case.defense, reason=f"User Banned as Penalty of Case {self.case.id}: `{self.ban_text}`")
        self.case.guild.ban(self.case.defense(), reason=f"User Banned as Penalty of Case {self.case.id}: `{self.ban_text}`")
        print(f"User Banned as Penalty of Case {self.case.id}: `{self.ban_text}`")

class PrisonPenalty(Penalty):
    def __init__(self, case):
        super().__init__(case)
        self.prison_length_seconds = None
        return

    def New(self, prison_length_seconds: int):
        self.prison_length_seconds = prison_length_seconds
        return self
    
    def describe(self):
        if self.prison_length_seconds > 0:
            return f"Prison: {utils.seconds_to_time_long(self.prison_length_seconds)}"
        else:
            return f"Prison: Permanent / Indefinite"
        
    async def Execute(self):
        await warden.newWarrant(self.case.defense(), "case", f"Case {self.case.id} Verdict", self.case.plaintiff_id, self.prison_length_seconds)

def penaltyFromDict(case, d: dict) -> Penalty:
    # dynamically locate the class and instantiate it
    for subclass in Penalty.__subclasses__():
        if subclass.__name__ == d["type"]:
            new_penalty = subclass(case)
            # assign all the values from the dictionary to the new penalty
            for key in d:
                new_penalty.__dict__[key] = d[key]
            return new_penalty