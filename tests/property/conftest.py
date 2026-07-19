"""Hypothesis 属性测试配置。"""
from hypothesis import settings

settings.register_profile(
    "ci",
    max_examples=20,
    deadline=None,
    suppress_health_check=[],  # 全开健康检查
)
settings.register_profile(
    "dev",
    max_examples=100,
    deadline=None,
)
settings.load_profile("ci")  # CI 跑得快，dev 详细