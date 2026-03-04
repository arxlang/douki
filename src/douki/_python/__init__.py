"""
title: Python language backend for Douki.
"""

from douki._base.language import register_language
from douki._python.language import PythonLanguage

register_language(PythonLanguage)
