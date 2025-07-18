import enum

class CheckpointState(str, enum.Enum):
    PROCESS_PENDING = "PROCESS_PENDING"
    PROCESSED = "PROCESSED"
    EMBEDDED = "EMBEDDED"
    DELETED = "DELETED"
    PROCESS_ERROR = "PROCESS_ERROR"
    EMBED_ERROR = "EMBED_ERROR"
    ERROR = "ERROR"