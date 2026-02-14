from sqlalchemy import Column, Integer, String, Float, JSON, DateTime, ForeignKey, Enum
from sqlalchemy.orm import relationship
from datetime import datetime
from sqlalchemy.ext.declarative import declarative_base
import enum


Base = declarative_base()

class MotionCategory(str, enum.Enum):
    MOVE = "move"
    GET = "get"
    PUT = "put"
    REACH = "reach"
    GRASP = "grasp"
    WALK = "walk"
    BEND = "bend"
    SIT = "sit"
    STAND = "stand"
    EYE_ACTION = "eye_action"

class Motion(Base):
    __tablename__ = "motions"

    id = Column(Integer, primary_key=True, index=True)
    code = Column(String, unique=True, index=True) # e.g. "M3", "G1",etc
    category = Column(String) # e.g. "move", "get", etc.
    description = Column(String)
    body_region = Column(String) # e.g. "arm", "finger", etc
    mod_value = Column(Float) # the time value unit (MOD)
    time_seconds = Column(Float) # mod_value * 0.129

class Study(Base):
    __tablename__ = "studies"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    description = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    study_motions = relationship("StudyMotion", back_populates="study")
    

class StudyMotion(Base):
    __tablename__ = "study_motions"

    id = Column(Integer, primary_key=True, index=True)
    study_id = Column(Integer, ForeignKey("studies.id"))
    motion_code = Column(String)
    sequence_order = Column(Integer)  # Order in the sequence
    quantity = Column(Integer, default=1)  # How many times this motion repeats

    # Relationships
    study = relationship("Study", back_populates="study_motions")