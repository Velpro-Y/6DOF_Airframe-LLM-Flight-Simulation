import matlab.engine
import logging

from config import *

logger = logging.getLogger(__name__)

_engine = None


def get_engine():

    global _engine

    if _engine is not None:
        return _engine

    logger.info("Connecting MATLAB...")

    names = matlab.engine.find_matlab()

    if not names:
        raise RuntimeError(
            "请先在MATLAB执行 matlab.engine.shareEngine"
        )

    _engine = matlab.engine.connect_matlab(names[0])

    _engine.cd(str(SIMULINK_DIR), nargout=0)

    _engine.load_system(str(MODEL_FILE), nargout=0)

    logger.info("MATLAB Ready.")

    return _engine