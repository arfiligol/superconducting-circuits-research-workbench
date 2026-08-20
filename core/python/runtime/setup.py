from pathlib import Path
from shutil import copytree, rmtree

from setuptools import setup
from setuptools.command.build_py import build_py
from setuptools.command.sdist import sdist


def _ignore_julia_build_state(_directory: str, names: list[str]) -> set[str]:
    return {
        name for name in names if name in {".git", "__pycache__", "test"} or name.endswith(".pyc")
    }


def _schemdraw_library_source() -> Path:
    packaged = Path(__file__).resolve().parent / "schemdraw_circuit_library"
    return (
        packaged
        if packaged.is_dir()
        else Path(__file__).resolve().parents[1] / "circuit_libraries" / "schemdraw_circuit_library"
    )


class BuildPyWithJulia(build_py):
    """Bundle the pinned Julia runtime used by git-pinned consumer installs."""

    def run(self) -> None:
        super().run()
        core = Path(__file__).resolve().parents[2]
        packaged = Path(__file__).resolve().parent / "superconducting_circuits_runtime" / "_julia"
        source = core / "julia" if (core / "julia").is_dir() else packaged
        destination = Path(self.build_lib) / "superconducting_circuits_runtime" / "_julia"
        if destination.exists():
            rmtree(destination)
        for package in ("SuperconductingCircuitsCore", "SuperconductingCircuitsRunner"):
            copytree(
                source / package,
                destination / package,
                dirs_exist_ok=True,
                ignore=_ignore_julia_build_state,
            )
        copytree(
            _schemdraw_library_source(),
            Path(self.build_lib) / "schemdraw_circuit_library",
            dirs_exist_ok=True,
            ignore=_ignore_julia_build_state,
        )


class SdistWithJulia(sdist):
    """Carry the owned Julia projects into the runtime sdist before wheel building."""

    def make_release_tree(self, base_dir: str, files: list[str]) -> None:
        super().make_release_tree(base_dir, files)
        core = Path(__file__).resolve().parents[2] / "julia"
        destination = Path(base_dir) / "superconducting_circuits_runtime" / "_julia"
        for package in ("SuperconductingCircuitsCore", "SuperconductingCircuitsRunner"):
            copytree(
                core / package,
                destination / package,
                dirs_exist_ok=True,
                ignore=_ignore_julia_build_state,
            )
        copytree(
            Path(__file__).resolve().parents[1] / "circuit_libraries" / "schemdraw_circuit_library",
            Path(base_dir) / "schemdraw_circuit_library",
            dirs_exist_ok=True,
            ignore=_ignore_julia_build_state,
        )


setup(cmdclass={"build_py": BuildPyWithJulia, "sdist": SdistWithJulia})
