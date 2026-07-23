"""步骤自动发现"""
import importlib
import pkgutil
import inspect
from pathlib import Path
from .base import PipelineStep


def discover_steps(package_path: str | None = None) -> list[type[PipelineStep]]:
    """自动发现 steps/ 下所有 PipelineStep 实现

    扫描当前包中所有模块，收集 PipelineStep 子类，
    按模块名（stepN_xxx）排序。
    """
    if package_path is None:
        package_path = __package__ or __name__

    steps: list[type[PipelineStep]] = []
    package = importlib.import_module(package_path)
    pkg_path = Path(package.__file__).parent if package.__file__ else None

    if pkg_path and pkg_path.is_dir():
        for _importer, modname, _ispkg in pkgutil.iter_modules([str(pkg_path)]):
            if modname.startswith("_"):
                continue
            module = importlib.import_module(f".{modname}", package_path)
            for _name, obj in inspect.getmembers(module, inspect.isclass):
                if (obj is not PipelineStep
                        and issubclass(obj, PipelineStep)
                        and not getattr(obj, "__abstract__", False)
                        and hasattr(obj, "name")):
                    steps.append(obj)

    steps.sort(key=lambda s: s.__module__.split(".")[-1])
    return steps
