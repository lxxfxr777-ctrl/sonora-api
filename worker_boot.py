from __future__ import annotations

import uvicorn

import worker
from invidious_fallback import patch_worker


patch_worker(worker)


if __name__ == "__main__":
    uvicorn.run(
        worker.app,
        host="127.0.0.1",
        port=8787,
        reload=False,
    )
