from __future__ import annotations

from typing import *

if TYPE_CHECKING:
    from .casemanager import Case

import datetime

from ..stasilogging import *
from .penalties import *


class Motion:

    expiry_days = 1
    expiry_hours = expiry_days * 24

    Case: Case = None

    async def startVoting(self):
        self.Expiry = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=self.expiry_hours)
        self.Votes["Yes"] = []
        self.Votes["No"] = []
        self.Case.motion_in_consideration = self
        self.Case.event_log.append(await self.Case.newEvent(
            "motion_up",
            f"The motion {self.MotionID} has been put up to be considered for a vote by {self.Case.nameUserByID(self.Author.id)}.",
            f"""The motion {self.MotionID} has been put up to be considered for a vote by {self.Case.nameUserByID(self.Author.id)}. 
Unless another vote is rushed, voting will end on {discord_dynamic_timestamp(self.Expiry, 'F')}.""",
            motion = self.toDict()
        ))
    
    async def CancelVoting(self, reason:str = None):
        if not self.Expiry and self.Case.motion_in_consideration != self:
            return
        self.Expiry = None
        self.Case.motion_in_consideration = None
        self.Votes["Yes"] = []
        self.Votes["No"] = []
        explan = f"Voting for motion {self.MotionID} has been cancelled."
        if reason:
            explan += f"\nReason: {reason}"
        self.Case.event_log.append(await self.Case.newEvent(
            "motion_cancel_vote",
            f"Voting for motion {self.MotionID} has been cancelled.",
            explan,
            motion = self.toDict()
        ))

    async def VoteFailed(self):
        yes = ', '.join([self.Case.nameUserByID(user) for user in self.Votes["Yes"]])
        no = ', '.join([self.Case.nameUserByID(user) for user in self.Votes["No"]])
        self.Case.event_log.append(await self.Case.newEvent(
            "motion_failed",
            f"The motion {self.MotionID} has failed its vote.",
            f"The motion {self.MotionID} has failed its jury vote ({len(self.Votes['Yes'])}/{len(self.Votes['No'])}).\n\nIn Support: {yes}\n\nIn Opposition: {no}",
            motion = self.toDict()
        ))
        return

    async def VotePassed(self):
        yes = ', '.join([self.Case.nameUserByID(user) for user in self.Votes["Yes"]])
        no = ', '.join([self.Case.nameUserByID(user) for user in self.Votes["No"]])
        self.Case.event_log.append(await self.Case.newEvent(
            "motion_passed",
            f"The motion {self.MotionID} has passed its vote.",
            f"The motion {self.MotionID} has passed its jury vote ({len(self.Votes['Yes'])}/{len(self.Votes['No'])}).\n\nIn Support: {yes}\n\nIn Opposition: {no}",
            motion = self.toDict()
        ))
        return
    
    async def Execute(self):
        return
    
    def ReadyToClose(self) -> bool:
        if len(self.Votes["Yes"]) + len(self.Votes["No"]) >= len(self.Case.jury_pool_ids):
            return True
        if datetime.datetime.now(datetime.timezone.utc) > self.Expiry:
            return True
        return False

    async def Close(self, delete: bool = True):
        # DEBUG CODE REMOVE LATER

        print(f"Closing motion {self}")
        if len(self.Votes["No"]) >= len(self.Votes["Yes"]):
            await self.VoteFailed()
        else:
            await self.VotePassed()
            await self.Execute()
        if delete:
            self.Case.motion_queue.remove(self)
            if self.Case.motion_in_consideration == self:
                self.Case.motion_in_consideration = None

    # Close without executing, no matter what    
    def forceClose(self):
        self.Case.motion_queue.remove(self)
        if self.Case.motion_in_consideration == self:
            self.Case.motion_in_consideration = None

    def fromDict(self, DBDocument: dict):
        for key in DBDocument:
            setattr(self, key, DBDocument[key])
        return self
    
    async def New(self, author) -> Motion:  # the event log entry should be updated by the subtype's New() function
        self.Created = datetime.datetime.now(datetime.timezone.utc)
        self.Author = author
        self.MotionID = f"{self.Case.id}-M{self.Case.motion_number}"  # 11042023-M001 for example
        self.Case.motion_number += 1
        self.Case.motion_queue.append(self)
        return self

    def __init__(self, Case: Case):
        self.Case = Case
        self.Expiry = None  # this is set by the motion manageer based on when it appears on the floors
        self.Votes = {}
        self.Votes["Yes"] = []
        self.Votes["No"] = []
        self.MotionID = "#NO-ID-ERR"
        return 

    def __del__(self):
        # DEBUG CODE REMOVE LATER

        print(f"DEL CALLED FOR {self}")
        return
    
    def __str__(self):
        return self.MotionID

    def __repr__(self):
        return self.MotionID

    def toDict(self):  # like Motion.Save() but doesn't save the dictionary, just returns it instead. Motions are saved when their 
        save = self.__dict__
        save["type"] = self.__class__.__name__
        return save

class StatementMotion(Motion):
    
    def __init__(self, Case: Case):
        super().__init__(Case)
        self.statement_content = None

    async def Execute(self):
        self.Case.event_log.append(await self.Case.newEvent(
            "jury_statement",
            f"The jury has made an official statement.",
            f"Pursuant to motion {self.MotionID}, the Jury makes the following statement:\n{self.statement_content}",
            motion = self.toDict()
        ))
    
    async def New(self, author, statement_content: str):
        await super().New(author)
        self.statement_content = statement_content
        self.Case.event_log.append(await self.Case.newEvent(
            "propose_statement",
            f"Motion {self.MotionID} has been filed to make a statement.",
            f"Motion {self.MotionID} has been filed by {self.Case.nameUserByID(self.Author.id)} to have the jury make a statement.\nStatement: {statement_content}",
            motion = self.toDict()
        ))
        return self

    def fromDict(self, DBDocument: dict):
        super().fromDict(DBDocument)
        return

class OrderMotion(Motion):
    
    def __init__(self, Case: Case):
        super().__init__(Case)
        self.target = None
        self.order_content = None
    
    async def Execute(self):
        self.Case.event_log.append(await self.Case.newEvent(
            "jury_order",
            f"The jury has given a binding order.",
            f"Pursuant to motion {self.MotionID}, the Jury compels the following entity:\n{self.target}\n\nTo comply with the following order:\n{self.order_content}.\nNot following this order can result in penalties.",
            motion = self.toDict()
        ))

    async def New(self, author, target: str, order_content: str):
        await super().New(author)
        self.target = target
        self.order_content = order_content
        self.Case.event_log.append(await self.Case.newEvent(
            "propose_order",
            f"Motion {self.MotionID} has been filed to give a binding order.",
            f"Motion {self.MotionID} has been filed by {self.Case.nameUserByID(self.Author.id)} to compel the following entity: {target}\nTo comply with the following order:\n{order_content}.",
            motion = self.toDict()
        ))
        return self

class RushMotion(Motion):
    
    def __init__(self, case):
        self.Case = case
        self.Expiry = None  # this is set by the motion manageer based on when it appears on the floors
        self.Votes = {}
        self.Votes["Yes"] = []
        self.Votes["No"] = []
        self.MotionID = "#NO-ID-ERR"
        self.rushed_motion_id = None

    async def New(self, author, rushed_motion_id: str, explanation: str):
        # ported from the old code
        self.Created = datetime.datetime.now(datetime.timezone.utc)
        self.Author = author
        self.MotionID = f"{self.Case.id}-M{self.Case.motion_number}"  # 11042023-M001 for example
        self.Case.motion_number += 1

        # if someone accidentally passes a motion instead of just its id, no worries
        if isinstance(rushed_motion_id, Motion):
            motion = rushed_motion_id
        else:
            motion = self.Case.getMotionByID(rushed_motion_id)

        self.rushed_motion_id = motion.MotionID
        self.explanation = explanation
        self.Case.event_log.append(await self.Case.newEvent(
            "propose_rush_motion",
            f"Motion {self.MotionID} has been filed to rush {self.rushed_motion().MotionID}.",
            f"Motion {self.MotionID} has been filed by {self.Case.nameUserByID(self.Author.id)} to rush motion {self.rushed_motion().MotionID} for an immediate floor vote.\nReason: {explanation}",
            motion = self.toDict(),
            rushed_motion = self.rushed_motion().toDict()
        ))
        for motion in self.Case.motion_queue:
            await motion.CancelVoting(reason=f"Motion {self.MotionID} to rush motion {self.rushed_motion().MotionID} has been filed.")
        
        self.Case.motion_queue = [self] + self.Case.motion_queue
        return self

    def rushed_motion(self):
        return self.Case.getMotionByID(self.rushed_motion_id)

    async def Execute(self):
        self.Case.event_log.append(await self.Case.newEvent(
            "rush_motion",
            f"A motion {self.rushed_motion().MotionID} has been rushed to the front of the queue.",
            f"Pursuant to motion {self.MotionID}, {self.rushed_motion().MotionID} has been rushed to the front of the queue and will now face an immediate vote.",
            motion = self.toDict(),
            rushed_motion = self.rushed_motion().toDict()
        ))
        rushed = self.rushed_motion()
        self.Case.motion_queue.remove(rushed)
        for motion in self.Case.motion_queue:
            if motion == self:
                continue
            await motion.CancelVoting(reason=f"Motion {rushed.MotionID} has been rushed to a vote.")
        self.Case.motion_queue = [rushed] + self.Case.motion_queue
        self.rushed_motion().startVoting()
        

# this motion can batch pass or deny any set of motions
# it is not placed at the end of the queue, rather it is placed 
# before the first motion referenced

class BatchVoteMotion(Motion):
    
    def __init__(self, case):
        super().__init__(case)
    
    async def New(self, author, pass_motion_ids: List[str], deny_motion_ids: List[str], reason: str):
        self.Created = datetime.datetime.now(datetime.timezone.utc)
        self.Author = author
        self.MotionID = f"{self.Case.id}-M{self.Case.motion_number}"  # 11042023-M001 for example
        self.Case.motion_number += 1

        # check if pass_motion_ids and deny_motion_ids are None and change them to []

        if pass_motion_ids is None:     pass_motion_ids = []
        if deny_motion_ids is None:     deny_motion_ids = []

        # you can pass a single motion id instead of a list with 1 item and they will be processed automatically
        if not isinstance(pass_motion_ids, list):       pass_motion_ids = [pass_motion_ids]
        if not isinstance(deny_motion_ids, list):       deny_motion_ids = [deny_motion_ids]
        
        aggregate = pass_motion_ids + deny_motion_ids
        for motion_id in aggregate:
            motion = self.Case.getMotionByID(motion_id)
            if not motion:
                print(self.Case.motion_queue)
                raise Exception(f"Motion {motion_id} does not exist.")
        
        self.pass_motion_ids = pass_motion_ids
        self.deny_motion_ids = deny_motion_ids
        self.reason = reason

        execute_str = ""
        if pass_motion_ids:
            execute_str += f"The following motions will be passed: {','.join(pass_motion_ids)}\n"
        
        if deny_motion_ids:
            execute_str += f"The following motions will be denied: {','.join(deny_motion_ids)}\n"


        self.Case.event_log.append(await self.Case.newEvent(
            "propose_summary_motion",
            f"Motion {self.MotionID} has been filed to pass or deny motions.",
            f"Motion {self.MotionID} has been filed by {self.Case.nameUserByID(self.Author.id)}.\n{execute_str}\nReason: {reason}",
            motion = self.toDict()
        ))

        # add to queue in front of first motion referenced
        for motion in self.Case.motion_queue:
            if motion.MotionID in aggregate:
                index = self.Case.motion_queue.index(motion)
                if index == 0:
                    self.Case.motion_in_consideration.CancelVoting(reason=f"Motion {self.MotionID} has been filed to pass or deny a set of motions.")
                self.Case.motion_queue.insert(self.Case.motion_queue.index(motion), self)
                break
        return self

    async def Execute(self):

        passed = []
        failed = []
        not_found = []
        
        for motion_id in self.pass_motion_ids:
            motion = self.Case.getMotionByID(motion_id)
            if not motion:
                not_found.append(motion_id)
                continue
            passed.append(motion_id)
            await motion.Execute()
            await motion.forceClose()

        for motion_id in self.deny_motion_ids:
            motion = self.Case.getMotionByID(motion_id)
            if not motion:
                not_found.append(motion_id)
                continue
            failed.append(motion_id)
            motion.forceClose()
        
        executed_str = ""
        if passed:
            executed_str += f"The following motions have been passed: {','.join(passed)}\n"
        
        if failed:
            executed_str += f"The following motions have been denied: {','.join(failed)}\n"
        
        if not_found:
            executed_str += f"The following motions were referenced, but not found: {','.join(not_found)}"

        self.Case.event_log.append(await self.Case.newEvent(
            "batch_motion",
            f"Execution on Batch Vote Motion {self.MotionID} has finished.",
            f"Pursuant to motion {self.MotionID}, the following has been executed:\n{executed_str}",
            motion = self.toDict(),
            not_found = not_found,
            passed = passed,
            failed = failed
        ))
        
class AdjustPenaltyMotion(Motion):
    """
    Adjusts the penalty if the case is delivered a guilty verdict.
    This is a WIP, as the way the penalty is tracked and managed may change down the line.
    """

    def __init__(self, case):
        super().__init__(case)
        self.reason: str = None
        self.new_penalties: dict = None

    async def New(self, author, new_penalties: List[Penalty], reason: str) -> Motion:
        await super().New(author)

        if isinstance(new_penalties, Penalty):
            new_penalties = [new_penalties]

        self.reason = reason
        self.new_penalties = new_penalties

        old_penalty_str = self.Case.describePenalties(self.Case.penalties)
    
        new_penalties_str = self.Case.describePenalties(new_penalties)

        self.Case.event_log.append(await self.Case.newEvent(
            "propose_new_penalty",
            f"Motion {self.MotionID} has been filed to adjust the Penalty if found guilty.",
            f"Motion {self.MotionID} has been filed by {self.Case.nameUserByID(self.Author.id)} to adjust the penalty of a guilty verdict From:\n{old_penalty_str}\n\nTo:\n{new_penalties_str}\nReason: {reason}",
            motion = self.toDict(),
            old_penalties = [penalty.toDict() for penalty in self.Case.penalties],
            new_penalties = [penalty.toDict() for penalty in new_penalties]
        ))
        return self
    
    async def Execute(self):

        old_penalty_str = self.Case.describePenalties(self.Case.penalties)
    
        new_penalties_str = self.Case.describePenalties(self.new_penalties)
    
        old_penalties = [penalty.toDict() for penalty in self.Case.penalties]
        
        self.Case.penalties = self.new_penalties

        self.Case.event_log.append(await self.Case.newEvent(
            "new_penalty",
            f"The Penalty of the Case has been adjusted.",
            f"Pursuant to motion {self.MotionID}, the guilty penalty has been adjusted From:\n{old_penalty_str}\n\nTo:\n{new_penalties_str}",
            motion = self.toDict(),
            old_penalties = old_penalties,
            new_penalties = [penalty.save() for penalty in self.new_penalties]
        ))

    
def loadMotionFromDict(case, motion_dict):
    for subtype in Motion.__subclasses__():
        if motion_dict["type"] == subtype.__name__:
            return subtype(case).fromDict(motion_dict)