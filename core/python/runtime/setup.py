from pathlib import Path
from shutil import copytree, rmtree

from setuptools import setup
from setuptools.command.build_py import build_py


class BuildPyWithJulia(build_py):
    """Bundle the pinned Julia runtime used by git-pinned consumer installs."""

    def run(self) -> None:
        super().run()
        core = Path(__file__).resolve().parents[2]
        destination = Path(self.build_lib) / "superconducting_circuits_runtime" / "_julia"
        if destination.exists():
            rmtree(destination)
        for package in ("SuperconductingCircuitsCore", "SuperconductingCircuitsRunner"):
            copytree(
                core / "julia" / package,
                destination / package,
                dirs_exist_ok=True,
                ignore=lambda _directory, names: {
                    name
                    for name in names
                    if name in {".git", "__pycache__", "test"} or name.endswith(".pyc")
                },
            )


setup(cmdclass={"build_py": BuildPyWithJulia})
