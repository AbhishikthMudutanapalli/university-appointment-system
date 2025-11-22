
# ============================================
# Configuration file for University Appointment System
# Contains database configuration and Flask settings
# ============================================
import os

BASE_DIR = os.path.abspath(os.path.dirname(__file__))

class Config:
    SECRET_KEY = "change-this-secret-key"  # change for production
    SQLALCHEMY_DATABASE_URI = "sqlite:///" + os.path.join(BASE_DIR, "app.db")
    SQLALCHEMY_TRACK_MODIFICATIONS = False

