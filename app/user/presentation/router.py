from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from db.session import get_db
from shared.auth import create_access_token
from shared.exceptions import ConflictError, UnauthorizedError
from shared.http import handle_domain_error
from user.application.create_user import CreateUser
from user.application.login_user import LoginUser
from user.domain.entities.user import User
from user.domain.ports.user_repository import UserRepository
from user.infrastructure.repositories.user_repository_impl import UserRepositoryImpl
from user.presentation.deps import get_current_user
from user.presentation.schemas.user_schema import (
    LoginResponseSchema,
    UserCreateSchema,
    UserLoginSchema,
    UserResponseSchema,
)

router = APIRouter(prefix="/users", tags=["usuarios"])


def get_user_repository(session: Session = Depends(get_db)) -> UserRepository:
    return UserRepositoryImpl(session)


@router.get("", response_model=list[UserResponseSchema])
def list_users(
    repository: UserRepository = Depends(get_user_repository),
    _current_user: User = Depends(get_current_user),
) -> list[UserResponseSchema]:
    return [UserResponseSchema.from_entity(user) for user in repository.all()]


@router.post("", response_model=UserResponseSchema, status_code=status.HTTP_201_CREATED)
def create_user(
    payload: UserCreateSchema,
    repository: UserRepository = Depends(get_user_repository),
    _current_user: User = Depends(get_current_user),
) -> UserResponseSchema:
    try:
        user = CreateUser(repository).execute(email=payload.email, password=payload.password)
    except ConflictError as exc:
        handle_domain_error(exc)
    return UserResponseSchema.from_entity(user)


@router.post("/login", response_model=LoginResponseSchema)
def login_user(
    payload: UserLoginSchema,
    repository: UserRepository = Depends(get_user_repository),
) -> LoginResponseSchema:
    try:
        user = LoginUser(repository).execute(email=payload.email, password=payload.password)
    except UnauthorizedError as exc:
        handle_domain_error(exc)
    token = create_access_token(user_id=user.id, email=user.email, remember=payload.remember)
    return LoginResponseSchema(access_token=token, user=UserResponseSchema.from_entity(user))


@router.get("/me", response_model=UserResponseSchema)
def get_me(current_user: User = Depends(get_current_user)) -> UserResponseSchema:
    return UserResponseSchema.from_entity(current_user)
