import enum

class CheckpointState(str, enum.Enum):
    PROCESS_PENDING = "PROCESS_PENDING"
    PROCESSED = "PROCESSED"
    EMBEDDED = "EMBEDDED"
    DELETED = "DELETED"
    ERROR = "ERROR"