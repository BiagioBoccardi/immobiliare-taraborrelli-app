"""Events emitted by the auth service."""

import uuid

from py_common.events.base import EventPayload


class UserDeletedV1(EventPayload):
    """A user asked to be erased: every service must delete the data linked to `user_id`."""

    event_type = "auth.user_deleted"
    version = 1

    user_id: uuid.UUID
