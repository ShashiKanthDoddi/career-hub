"""state module of Career Hub. See MAP.md for what lives where."""


CURRENT_JOB = {"company": "", "title": "", "desc": ""}


RESUME_CACHE = {"text": None}


MAIL = {"busy": False, "progress": ""}


JOB = {"ctx": None}


PW = {"p": None}


TASKS = set()

FIND_DIAG = {}         # counts from the last job search, shown on Find jobs
UPDATE = {"manifest": None}   # latest release found by the updater
APP = {"restart": False}      # set by api_restart
