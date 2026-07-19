"""P2-C-T2 烟雾测试：openai SDK 接入验证（不实际网络调用）。"""
import os
import pytest
from openai import OpenAI


def test_openai_sdk_importable():
    """openai SDK 可导入。"""
    from openai import OpenAI as _OpenAI
    assert _OpenAI is not None


def test_openai_client_constructable_with_deepseek_base_url():
    """OpenAI 客户端可用 DeepSeek base_url 构造（不实际调用）。"""
    client = OpenAI(
        api_key=os.environ.get('DEEPSEEK_API_KEY', 'sk-dummy'),
        base_url='https://api.deepseek.com',
        timeout=60,
    )
    assert str(client.base_url).startswith('https://api.deepseek.com')


def test_openai_client_lazy_no_network():
    """OpenAI 客户端构造时不立即校验 API key（惰性）。"""
    # 即便 API key 无效也能构造（SDK 懒校验）
    client = OpenAI(api_key='sk-dummy-invalid', base_url='https://api.deepseek.com')
    assert client is not None
