"""Shared robot-runtime helpers for both server frontends.

``server.py`` (FastMCP/stdio) and ``server_openai.py`` (FastAPI/HTTP) used to
carry byte-identical copies of these five helpers — the daemon HTTP client, the
pose builder, and the tool-repository loaders. They now live here once and are
imported by both, so a fix to loading/dispatch logic is made in a single place.

This module pulls in the ``[server]`` extra (``httpx``) and talks to a live
daemon, so it is coverage-excluded just like the server modules (see
``pyproject.toml`` ``omit`` / ``sonar-project.properties``).
"""

import importlib.util
import json
import math
import os
from pathlib import Path
from typing import Any, Dict, Optional

import httpx
from dotenv import load_dotenv

# Load .env here, before REACHY_BASE_URL is captured below. Both servers also
# call load_dotenv(), but they import this module first — so the capture would
# otherwise run before their load_dotenv() and ignore a .env-defined base URL.
load_dotenv()

# Configuration shared by both servers.
REACHY_BASE_URL = os.getenv("REACHY_BASE_URL", "http://localhost:8000")
TOOLS_REPOSITORY_PATH = Path(__file__).parent / "tools_repository"


def create_head_pose(
    x: float = 0.0,
    y: float = 0.0,
    z: float = 0.0,
    roll: float = 0.0,
    pitch: float = 0.0,
    yaw: float = 0.0,
    degrees: bool = False,
    mm: bool = False,
) -> Dict[str, Any]:
    """
    Create a head pose configuration for Reachy Mini.

    Args:
        x, y, z: Position offsets (meters by default, mm if mm=True)
        roll, pitch, yaw: Rotation angles (radians by default, degrees if degrees=True)
        degrees: If True, angles are in degrees
        mm: If True, positions are in millimeters

    Returns:
        Dictionary with head pose configuration
    """
    if mm:
        x, y, z = x / 1000, y / 1000, z / 1000

    if degrees:
        roll = math.radians(roll)
        pitch = math.radians(pitch)
        yaw = math.radians(yaw)

    return {
        "x": x,
        "y": y,
        "z": z,
        "roll": roll,
        "pitch": pitch,
        "yaw": yaw,
    }


async def make_request(
    method: str,
    endpoint: str,
    json_data: Optional[Dict] = None,
    params: Optional[Dict] = None,
) -> Dict[str, Any]:
    """Make an HTTP request to the Reachy Mini daemon."""
    url = f"{REACHY_BASE_URL}{endpoint}"

    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            if method.upper() == "GET":
                response = await client.get(url, params=params)
            elif method.upper() == "POST":
                response = await client.post(url, json=json_data)
            elif method.upper() == "PUT":
                response = await client.put(url, json=json_data)
            elif method.upper() == "DELETE":
                response = await client.delete(url)
            else:
                raise ValueError(f"Unsupported HTTP method: {method}")

            response.raise_for_status()
            return response.json() if response.content else {"status": "success"}

        except httpx.HTTPError as e:
            return {"error": str(e), "status": "failed"}


def load_tool_index() -> Dict[str, Any]:
    """Load the tool index from tools_index.json."""
    index_path = TOOLS_REPOSITORY_PATH / "tools_index.json"
    if not index_path.exists():
        raise FileNotFoundError(f"Tool index not found at {index_path}")

    with open(index_path, "r") as f:
        return json.load(f)


def load_tool_definition(definition_file: str) -> Dict[str, Any]:
    """Load a tool definition from a JSON file."""
    def_path = TOOLS_REPOSITORY_PATH / definition_file
    if not def_path.exists():
        raise FileNotFoundError(f"Tool definition not found at {def_path}")

    with open(def_path, "r") as f:
        return json.load(f)


def load_script_module(script_file: str):
    """Dynamically load a Python script as a module."""
    script_path = TOOLS_REPOSITORY_PATH / "scripts" / script_file
    if not script_path.exists():
        raise FileNotFoundError(f"Script not found at {script_path}")

    spec = importlib.util.spec_from_file_location("tool_script", script_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module
