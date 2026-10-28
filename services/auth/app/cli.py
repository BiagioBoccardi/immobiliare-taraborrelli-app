"""Command line tools.

Create the first administrator (password read from the terminal, never from arguments):

    uv run python -m app.cli create-admin --email admin@example.com --name "Nome Cognome"
"""

import argparse
import asyncio
import getpass
import logging
import sys

from py_common.errors import ConflictError
from pydantic import TypeAdapter, ValidationError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.config import get_settings
from app.core.database import create_engine, create_session_factory
from app.core.security import PasswordHasher
from app.repositories.unit_of_work import SqlUnitOfWork
from app.schemas.common import Email, Password, PersonName
from app.services.users import UserAdminService

logger = logging.getLogger(__name__)


async def create_admin(email: str, password: str, full_name: str, database_url: str) -> str:
    engine = create_engine(database_url)
    try:
        async with create_session_factory(engine)() as session:
            service = UserAdminService(SqlUnitOfWork(session), PasswordHasher())
            user = await service.create_initial_admin(email, password, full_name)
            return str(user.id)
    finally:
        await engine.dispose()


async def ensure_initial_admin(
    session_factory: async_sessionmaker[AsyncSession], email: str, password: str, full_name: str
) -> bool:
    """Creates the first administrator at startup if none exists. Returns True if created.

    Invalid values are reported in the log without stopping the service.
    """
    try:
        valid_email = TypeAdapter(Email).validate_python(email)
        valid_name = TypeAdapter(PersonName).validate_python(full_name)
        TypeAdapter(Password).validate_python(password)
    except ValidationError:
        logger.error("initial administrator not created: invalid email, name or password")
        return False
    async with session_factory() as session:
        service = UserAdminService(SqlUnitOfWork(session), PasswordHasher())
        try:
            await service.create_initial_admin(valid_email, password, valid_name)
        except ConflictError:
            return False
    logger.info("initial administrator created")
    return True


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="app.cli")
    sub = parser.add_subparsers(dest="command", required=True)
    admin = sub.add_parser("create-admin", help="Create the first administrator")
    admin.add_argument("--email", required=True)
    admin.add_argument("--name", required=True)
    args = parser.parse_args(argv)

    password = getpass.getpass("Password (min 10 characters): ")
    try:
        email = TypeAdapter(Email).validate_python(args.email)
        name = TypeAdapter(PersonName).validate_python(args.name)
        TypeAdapter(Password).validate_python(password)
    except ValidationError as exc:
        print(f"Invalid input: {exc.errors()[0]['msg']}", file=sys.stderr)
        return 2
    try:
        user_id = asyncio.run(create_admin(email, password, name, get_settings().database_url))
    except ConflictError as exc:
        print(exc.message, file=sys.stderr)
        return 1
    print(f"Administrator created: {user_id}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
