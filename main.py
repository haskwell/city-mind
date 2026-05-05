#!/usr/bin/env python3
"""
CityMind - Main entry point for the city planning visualization application.
"""

import sys
import os

# Add the current directory to Python path to import modules from subdirectories
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from UI.city_graph_ui import launch


def main():
    """Main function to launch the CityMind UI application."""
    print("Starting CityMind - City Planning Visualization Tool...")
    launch()


if __name__ == "__main__":
    main()
