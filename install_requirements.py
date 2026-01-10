#!/usr/bin/env python3
"""
install_requirements.py

Create a virtual environment (optional) and install Python dependencies from a requirements file.

Behavior change:
- Relative paths for --requirements and --venv are now resolved relative to the script's directory
  (the location of this file) instead of the current working directory. This prevents accidental
  writes to C:\Windows\System32 when you run the script from an elevated shell whose cwd is System32.

Features:
- Creates a virtualenv (default ./venv next to this script) using the current Python or a specified Python executable.
- Generates a default requirements.txt (if none) matching this project.
- Uses the venv's python -m pip install -r <requirements> so pip inside the venv is used.
- Works on POSIX and Windows.
- Helpful logging and clear exit codes.

Usage:
  # Use requirements.txt next to this script and create venv next to script (non-interactive)
  python install_requirements.py --yes

  # Specify exact requirements path and venv path
  python install_requirements.py --requirements "C:\Users\DeathStar\Documents\nasabackup\tool\requirements.txt" --venv "C:\Users\DeathStar\Documents\nasabackup\tool\venv" --yes

  # Auto-create requirements if missing
  python install_requirements.py --auto-create --yes
"""

from __future__ import annotations
import argparse
import logging
import os
import shutil
import subprocess
import sys
import venv
from pathlib import Path
from typing import Optional

# Default requirements for this project (includes optional extras)
DEFAULT_REQUIREMENTS_CONTENT = """# Requirements for NASA Image Downloader
requests>=2.28.0,<3.0
tqdm>=4.60.0,<5.0
Pillow>=9.0.0,<10.0
boto3>=1.26.0,<2.0
"""

logger = logging.getLogger("install_requirements")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s: %(message)s")


def ensure_python_version(min_major: int = 3, min_minor: int = 8) -> None:
    if sys.version_info < (min_major, min_minor):
        logger.warning(
            "Running on Python %s.%s but project recommends Python %s.%s+. "
            "Script will continue but you may encounter compatibility issues.",
            sys.version_info.major,
            sys.version_info.minor,
            min_major,
            min_minor,
        )


def create_requirements_file(req_path: Path, content: str = DEFAULT_REQUIREMENTS_CONTENT) -> None:
    if req_path.exists():
        logger.info("Using existing requirements file: %s", req_path)
        return
    try:
        req_path.parent.mkdir(parents=True, exist_ok=True)
        req_path.write_text(content, encoding="utf-8")
        logger.info("Created default requirements file at %s", req_path)
    except Exception:
        logger.exception("Failed to create requirements file at %s", req_path)
        raise


def create_virtualenv(venv_dir: Path, python_exec: Optional[str] = None) -> None:
    if venv_dir.exists():
        logger.info("Virtualenv directory already exists: %s", venv_dir)
        return

    logger.info("Creating virtual environment at %s", venv_dir)
    try:
        if python_exec:
            subprocess.run([python_exec, "-m", "venv", str(venv_dir)], check=True)
        else:
            venv.EnvBuilder(with_pip=True).create(str(venv_dir))
        logger.info("Virtual environment created at %s", venv_dir)
    except subprocess.CalledProcessError:
        logger.exception("Failed to create virtualenv using %s", python_exec)
        raise
    except Exception:
        logger.exception("Failed to create virtualenv via venv module")
        raise


def get_venv_python(venv_dir: Path) -> Path:
    if os.name == "nt":
        return venv_dir / "Scripts" / "python.exe"
    else:
        return venv_dir / "bin" / "python"


def run_pip_install(python_executable: Path, requirements: Path, upgrade_pip: bool, extra_args: Optional[list] = None) -> None:
    if not python_executable.exists():
        raise FileNotFoundError(f"Python executable not found: {python_executable}")

    if upgrade_pip:
        logger.info("Upgrading pip in venv using %s", python_executable)
        try:
            subprocess.run([str(python_executable), "-m", "pip", "install", "--upgrade", "pip"], check=True)
        except subprocess.CalledProcessError:
            logger.warning("Failed to upgrade pip; proceeding with install anyway")

    cmd = [str(python_executable), "-m", "pip", "install", "-r", str(requirements)]
    if extra_args:
        cmd.extend(extra_args)

    logger.info("Installing requirements from %s using %s", requirements, python_executable)
    try:
        subprocess.run(cmd, check=True)
        logger.info("Requirements installed successfully.")
    except subprocess.CalledProcessError:
        logger.exception("pip install failed (command: %s)", " ".join(cmd))
        raise


def install_system_requirements(requirements: Path, upgrade_pip: bool) -> None:
    python_executable = Path(sys.executable)
    logger.warning("Installing requirements into the current Python environment: %s", python_executable)
    run_pip_install(python_executable, requirements, upgrade_pip)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Create a venv and install requirements for the NASA downloader project.")
    p.add_argument("--requirements", "-r", default="requirements.txt", help="Path to requirements.txt (will be created if missing). Relative paths are resolved relative to this script's directory.")
    p.add_argument("--venv", "-v", default="venv", help="Path to virtualenv directory to create/use (default: ./venv relative to this script).")
    p.add_argument("--python-exec", "--python", default=None, help="Python executable to use when creating the venv (e.g. python3.10).")
    p.add_argument("--system", action="store_true", help="Install into the current Python environment instead of creating a venv.")
    p.add_argument("--upgrade-pip", action="store_true", help="Run 'python -m pip install --upgrade pip' before installing requirements.")
    p.add_argument("--yes", "-y", action="store_true", help="Assume yes for prompts / run non-interactively.")
    p.add_argument("--remove-venv", action="store_true", help="If set and venv exists, remove it first (useful to start fresh).")
    p.add_argument("--auto-create", action="store_true", help="Automatically create the requirements file if missing (no prompt).")
    return p.parse_args()


def resolve_paths(req_arg: str, venv_arg: str) -> Tuple[Path, Path]:
    """
    Resolve paths relative to the script directory for relative inputs.
    Absolute inputs are used as-is.
    """
    script_dir = Path(__file__).parent.resolve()
    req_path = Path(req_arg)
    if not req_path.is_absolute():
        req_path = (script_dir / req_path).resolve()
    venv_path = Path(venv_arg)
    if not venv_path.is_absolute():
        venv_path = (script_dir / venv_path).resolve()
    return req_path, venv_path


def main() -> int:
    args = parse_args()
    try:
        ensure_python_version(3, 8)

        # Resolve paths relative to this script's directory (fixes System32 prompt)
        req_path, venv_dir = resolve_paths(args.requirements, args.venv)
        logger.debug("Resolved requirements path: %s", req_path)
        logger.debug("Resolved venv path: %s", venv_dir)

        # Ensure requirements file exists or create it
        if not req_path.exists():
            if args.yes or args.auto_create:
                create_requirements_file(req_path)
            else:
                # Prompt user, but show resolved location explicitly
                resp = input(f"Requirements file {req_path} does not exist. Create it with default content? [Y/n]: ").strip().lower()
                if resp in ("", "y", "yes"):
                    create_requirements_file(req_path)
                else:
                    logger.error("No requirements file to install. Exiting.")
                    return 2

        # If user wants system install, skip venv creation
        if args.system:
            if not args.yes:
                resp = input("Proceed to install into current Python environment? This may require admin rights. [y/N]: ").strip().lower()
                if resp not in ("y", "yes"):
                    logger.info("User cancelled system install. Exiting.")
                    return 0
            install_system_requirements(req_path, args.upgrade_pip)
            return 0

        # Non-system: use venv
        if venv_dir.exists() and args.remove_venv:
            logger.info("Removing existing venv at %s", venv_dir)
            try:
                shutil.rmtree(venv_dir)
            except Exception:
                logger.exception("Failed to remove venv directory %s", venv_dir)
                return 3

        if not venv_dir.exists():
            if not args.yes:
                resp = input(f"Create virtualenv at {venv_dir}? [Y/n]: ").strip().lower()
                if resp not in ("", "y", "yes"):
                    logger.info("User cancelled venv creation. Exiting.")
                    return 0
            create_virtualenv(venv_dir, python_exec=args.python_exec)
        else:
            logger.info("Using existing virtualenv at %s", venv_dir)

        python_in_venv = get_venv_python(venv_dir)
        if not python_in_venv.exists():
            logger.error("Expected python executable not found in venv: %s", python_in_venv)
            return 4

        run_pip_install(python_in_venv, req_path, args.upgrade_pip)
        logger.info("All done. To activate the venv:")
        if os.name == "nt":
            logger.info(r"  %s\Scripts\activate", venv_dir)
        else:
            logger.info("  source %s/bin/activate", venv_dir)
        return 0

    except KeyboardInterrupt:
        logger.info("Interrupted by user.")
        return 130
    except Exception:
        logger.exception("Fatal error while installing requirements.")
        return 5


if __name__ == "__main__":
    sys.exit(main())