from dataclasses import dataclass
from enum import StrEnum, unique


@unique
class AssignmentReadType(StrEnum):
    UNKNOWN = "unknown"
    VIDEO = "activity_read_video"
    FILE = "activity_read_file"

@dataclass
class AssignmentReadVideoPayload:
    start: int
    end: int
    type: str = AssignmentReadType.VIDEO

    def __post_init__(self):
        if self.start >= self.end:
            raise ValueError("The start time must be less than the end time!")
        
        if self.end - self.start > 125:
            raise ValueError("The whole time must by less than 125s!")
        
@dataclass
class AssignmentReadFilePayload:
    upload: int
    type: str = AssignmentReadType.FILE