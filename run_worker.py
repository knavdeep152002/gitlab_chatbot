#!/usr/bin/env python3
"""
Script to run the GitLab scraper worker from the project root.
This ensures proper module imports.
"""

import sys
import os

# Add the current directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Import and run the worker
from gitlab_chatbot.workers.worker import scrape_gitlab

if __name__ == "__main__":
    print("🚀 Starting GitLab scraper worker...")
    scrape_gitlab() 