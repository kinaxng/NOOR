# Source Generated with Decompyle++
# File: models.pyc (Python 3.13)

import uuid
from datetime import datetime, timezone
from typing import Optional
from sqlalchemy import String, Integer, DateTime, Text, JSON, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column
from pydantic import BaseModel, ConfigDict, Field, field_validator
from app.core.database import Base
from app.tasks.job_phases import get_phase_group
# WARNING: Decompyle incomplete
