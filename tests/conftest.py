"""全局 pytest fixtures。"""
from pathlib import Path

import pytest


@pytest.fixture(scope="session")
def fixtures_dir() -> Path:
    """测试 fixtures 根目录。"""
    return Path(__file__).parent / "fixtures"


@pytest.fixture
def tiny_sample(fixtures_dir: Path) -> Path:
    """最小的样本 fixture（Task 7 创建）。"""
    return fixtures_dir / "tiny" / "sample.md"
