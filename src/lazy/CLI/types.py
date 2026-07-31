from dataclasses import dataclass
from enum import Enum, unique

from ..core.zjuAPI.types import AssignmentReadType


@unique
class AssignmentType(Enum):
    UNKOWN = 0
    ACTIVITY = 1
    FORMUN = 2
    EXAM = 3
    CLASSROOM = 4
    QUESTIONNAIRE = 5
    
@dataclass
class LegalFileType:
    video = [
        'avi',
        'flv',
        'm4v',
        'mkv',
        'mov',
        'mp4',
        '3gp',
        '3gpp',
        'mpg',
        'rm',
        'rmvb',
        'swf',
        'webm',
        'wmv'
    ]

    audio = [
        'mp3',
        'm4a',
        'wav',
        'wma'
    ]

    image = [
        'jpeg', 
        'jpg', 
        'png', 
        'gif', 
        'bmp', 
        'heic', 
        'webp'
    ]

    document = [
        'txt', 
        'pdf', 
        'csv', 
        'xls', 
        'xlsx', 
        'doc', 
        'ppt', 
        'pptx', 
        'docx', 
        'odp', 
        'ods', 
        'odt', 
        'rtf'
    ]

    archieve = [
        'zip',
        'rar',
        'tar'
    ]

    other = [
        'mat',
        'dwg',
        'm',
        'mlapp',
        'slx',
        'mlx'
    ]


@dataclass
class AssignmentReadTask:
    assignment_title: str
    assignment_id: int
    mode: AssignmentReadType
    resource_name: str
    resource_id: int