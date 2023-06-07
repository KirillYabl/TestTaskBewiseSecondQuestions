import collections
import contextlib
import logging
import typing
import urllib.parse
import uuid

import fastapi.logger
import fastapi.responses
import sqlalchemy.orm
import sqlalchemy.exc
import starlette.datastructures
import uvicorn

import data_models
import db_models
import scheduler


@contextlib.asynccontextmanager
async def lifespan(app: fastapi.FastAPI):
    background_scheduler = scheduler.start_scheduler()
    yield
    background_scheduler.shutdown()


app = fastapi.FastAPI(lifespan=lifespan)


def query_logger(query_id: uuid.UUID, message: str, function: typing.Callable):
    """Add :query_id: to logger message for understanding, with which query there was a problem"""
    function(f"{query_id}| {message}")


@app.post("/create_user")
async def create_user(
        user: data_models.User,
        db_session: sqlalchemy.orm.Session = fastapi.Depends(db_models.get_session)
) -> dict[str, typing.Any]:
    new_user = db_models.User(user_name=user.user_name)
    query_id = uuid.uuid4()
    query_logger(query_id, f"creating user, params={user.json()}", fastapi.logger.logger.debug)
    try:
        db_session.add(new_user)
        db_session.commit()
        query_logger(query_id, "user created", fastapi.logger.logger.debug)
    except sqlalchemy.exc.IntegrityError as e:
        db_session.rollback()
        if "User_user_name_key" in e.args[0]:
            query_logger(query_id, "user not created, name exists", fastapi.logger.logger.debug)
            raise fastapi.HTTPException(
                status_code=fastapi.status.HTTP_400_BAD_REQUEST,
                detail="User with this name of user already exists",
            )
        elif "User_user_token_key" in e.args[0]:
            # too rare case with uuid4, because of that not making recreation
            query_logger(query_id, "user not created, uuid4 duplicate", fastapi.logger.logger.warning)
            raise fastapi.HTTPException(
                status_code=fastapi.status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Something went wrong, try one more",
            )

    return data_models.UserModel.from_orm(new_user).dict()


@app.post("/convert_audio")
async def convert_audio(
        request: fastapi.Request,
        audio: fastapi.UploadFile,
        user_audio_info: data_models.PostUserAudio = fastapi.Depends(),
        db_session: sqlalchemy.orm.Session = fastapi.Depends(db_models.get_session)
) -> str:
    query_id = uuid.uuid4()
    query_logger(query_id, f"converting audio, params={user_audio_info.json()}", fastapi.logger.logger.debug)
    user = db_session.query(db_models.User).filter(
        db_models.User.user_id == user_audio_info.user_id
    ).first()
    if user is None or user and user.token != user_audio_info.token:
        # for security same error for wrong login (user_id) or password (token)
        query_logger(query_id, f"user not found, wrong id or token", fastapi.logger.logger.debug)
        raise fastapi.HTTPException(
            status_code=fastapi.status.HTTP_400_BAD_REQUEST,
            detail="Wrong id of user or token",
        )
    query_logger(query_id, f"user with this id and token found, reading audio", fastapi.logger.logger.debug)
    audio_file = await audio.read()
    query_logger(query_id, "audio read, saving", fastapi.logger.logger.debug)
    # for purpose of performance file just save here, and it will be converted in other process by schedule
    user_audio = db_models.UserAudio(user_id=user.user_id, file=audio_file)  # FIXME: make it async
    try:
        db_session.add(user_audio)
        db_session.commit()
    except sqlalchemy.exc.DatabaseError:
        db_session.rollback()
    query_logger(query_id, "audio saved", fastapi.logger.logger.debug)
    base_url = str(request.base_url)
    get_record_path = str(starlette.datastructures.URLPath("get_record"))
    get_record_full_path = urllib.parse.urljoin(base_url, get_record_path)
    encoded_params = urllib.parse.urlencode({
        "id": user_audio.audio_id,
        "user_id": user_audio.user_id,
    })

    return f"{get_record_full_path}?{encoded_params}"


@app.get("/record")
async def get_record(
        user_audio_info: data_models.GetUserAudio = fastapi.Depends(),
        db_session: sqlalchemy.orm.Session = fastapi.Depends(db_models.get_session)
) -> fastapi.responses.FileResponse:
    query_id = uuid.uuid4()
    query_logger(query_id, f"getting audio, params={user_audio_info.json()}", fastapi.logger.logger.debug)
    audio_raw = db_session.query(db_models.UserAudio).filter(
        db_models.UserAudio.user_id == user_audio_info.user_id,
        db_models.UserAudio.audio_id == user_audio_info.id
    ).first()

    if audio_raw is None:
        query_logger(query_id, "audio not found", fastapi.logger.logger.debug)
        raise fastapi.HTTPException(
            status_code=fastapi.status.HTTP_400_BAD_REQUEST,
            detail="Audio with this id and id of user not found",
        )

    if audio_raw.convert_status != db_models.UserAudio.ConvertStatus.finished:
        query_logger(query_id, "audio not converted yet", fastapi.logger.logger.debug)
        raise fastapi.HTTPException(
            status_code=fastapi.status.HTTP_423_LOCKED,
            detail=f"Record not ready, current status={audio_raw.convert_status.value}",
        )

    query_logger(query_id, "audio converted, return audio", fastapi.logger.logger.debug)
    return fastapi.responses.FileResponse(audio_raw.file.url)


def main():
    logging.basicConfig(level=data_models.settings.logging_level)
    uvicorn.run(app, host=data_models.settings.api_host, port=data_models.settings.api_port)


if __name__ == '__main__':
    main()
