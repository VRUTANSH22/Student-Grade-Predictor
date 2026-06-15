"""
conftest.py — Pytest configuration
====================================
Ensures the project root is on sys.path so all imports work correctly
when running pytest from any directory.
"""
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
