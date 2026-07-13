# SPDX-License-Identifier: BSD-3-Clause

import shutil
from typing import List


def missing_media_tools() -> List[str]:
    missing = []
    for executable in ("ffmpeg", "ffprobe"):
        if shutil.which(executable) is None:
            missing.append(executable)
    return missing
