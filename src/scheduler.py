import logging

import apscheduler.schedulers.background
import fastapi.logger
import pydub.exceptions

import db_models
import data_models


def convert_audios():
    db_session = next(db_models.get_session())
    audios_to_convert = db_session.query(db_models.UserAudio).filter(
        db_models.UserAudio.convert_status == db_models.UserAudio.ConvertStatus.pending.value
    )
    if data_models.settings.logging_level == logging.DEBUG:
        # it needs resources, only for debug
        fastapi.logger.logger.debug(f"found {audios_to_convert.count()} files")
    for audio in audios_to_convert:
        audio.convert_status = db_models.UserAudio.ConvertStatus.converting.value
        try:
            wav = pydub.AudioSegment.from_wav(audio.file.url)
            wav.export(audio.file.url, format="mp3")
            audio.convert_status = db_models.UserAudio.ConvertStatus.finished.value
            fastapi.logger.logger.debug(f"successfully convert file {audio.file.url}")
        except pydub.exceptions.CouldntDecodeError:
            audio.convert_status = db_models.UserAudio.ConvertStatus.not_valid.value
            fastapi.logger.logger.debug(f"file {audio.file.url} not valid")
        except (pydub.exceptions.PydubException, IndexError):
            audio.convert_status = db_models.UserAudio.ConvertStatus.error.value
            fastapi.logger.logger.debug(f"file {audio.file.url} other exception")
        finally:
            db_session.commit()


def start_scheduler() -> apscheduler.schedulers.background.BackgroundScheduler:
    background_scheduler = apscheduler.schedulers.background.BackgroundScheduler(daemon=True)
    background_scheduler.add_job(convert_audios, "interval", seconds=10)
    background_scheduler.start()
    return background_scheduler
