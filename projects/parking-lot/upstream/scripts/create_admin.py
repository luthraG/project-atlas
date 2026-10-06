"""Bootstrap the first admin user on a fresh database.

Auth is PIN-based and every user is created via an admin-only endpoint, so a
brand-new database has no way to create its first admin through the API.
Run this once after `alembic upgrade head`:

    uv run python scripts/create_admin.py --username admin --display-name "Admin" --pin 1234

Inside the `backend` container (dependencies already installed, no need for
`uv run`'s sync check):

    docker compose exec backend python scripts/create_admin.py \
        --username admin --display-name "Admin" --pin 1234

Refuses (without modifying anything) if a user with that username already
exists.
"""

import argparse
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.application.commands import CreateUserCommand
from app.application.user_service import UserService
from app.domain.errors import DomainValidationError, DuplicateUsernameError
from app.domain.user import UserRole
from app.infrastructure.database import async_session_factory
from app.infrastructure.repositories.user_repository import SqlAlchemyUserRepository
from app.infrastructure.security import Argon2PasswordHasher


async def _create_admin(command: CreateUserCommand) -> None:
    async with async_session_factory() as session:
        service = UserService(SqlAlchemyUserRepository(session), Argon2PasswordHasher())
        try:
            await service.create(command)
            await session.commit()
        except DuplicateUsernameError:
            print(f"User '{command.username}' already exists — nothing to do.")
            return
        except DomainValidationError as exc:
            print(f"Invalid PIN: {exc}")
            return

    print(f"Admin user '{command.username}' created.")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--username", required=True)
    parser.add_argument("--display-name", required=True)
    parser.add_argument("--pin", required=True, help="4 to 6 digits")
    args = parser.parse_args()

    command = CreateUserCommand(args.username, args.display_name, UserRole.ADMIN, args.pin)
    asyncio.run(_create_admin(command))


if __name__ == "__main__":
    main()
