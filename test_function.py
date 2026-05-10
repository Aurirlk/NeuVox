"""
功能测试脚本
测试所有 API 接口
"""
import httpx
import asyncio
import json

BASE_URL = "http://localhost:8000"


async def test_health():
    """测试健康检查"""
    print("\n" + "="*50)
    print("1. 测试健康检查接口")
    print("="*50)
    
    async with httpx.AsyncClient() as client:
        response = await client.get(f"{BASE_URL}/api/v1/health")
        
    print(f"状态码: {response.status_code}")
    print(f"响应: {json.dumps(response.json(), ensure_ascii=False, indent=2)}")
    return response.status_code == 200


async def test_providers():
    """测试提供商列表"""
    print("\n" + "="*50)
    print("2. 测试提供商列表接口")
    print("="*50)
    
    async with httpx.AsyncClient() as client:
        response = await client.get(f"{BASE_URL}/api/v1/providers")
        
    print(f"状态码: {response.status_code}")
    print(f"响应: {json.dumps(response.json(), ensure_ascii=False, indent=2)}")
    return response.status_code == 200


async def test_voices():
    """测试音色列表"""
    print("\n" + "="*50)
    print("3. 测试音色列表接口")
    print("="*50)
    
    async with httpx.AsyncClient() as client:
        response = await client.get(f"{BASE_URL}/api/v1/voices")
        
    print(f"状态码: {response.status_code}")
    print(f"响应: {json.dumps(response.json(), ensure_ascii=False, indent=2)}")
    return response.status_code == 200


async def test_text_chat():
    """测试文本对话"""
    print("\n" + "="*50)
    print("4. 测试文本对话接口")
    print("="*50)
    
    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.post(
            f"{BASE_URL}/api/v1/chat/text",
            json={
                "message": "你好，请介绍一下你自己",
                "history": []
            }
        )
        
    print(f"状态码: {response.status_code}")
    result = response.json()
    print(f"回复: {result.get('message', '无回复')}")
    print(f"音频路径: {result.get('audio_path', '无')}")
    return response.status_code == 200


async def test_crm_stats():
    """测试 CRM 统计"""
    print("\n" + "="*50)
    print("5. 测试 CRM 统计接口")
    print("="*50)
    
    async with httpx.AsyncClient() as client:
        response = await client.get(f"{BASE_URL}/api/v1/crm/stats")
        
    print(f"状态码: {response.status_code}")
    if response.status_code == 200:
        print(f"响应: {json.dumps(response.json(), ensure_ascii=False, indent=2)}")
    else:
        print(f"错误: {response.text}")
    return response.status_code == 200


async def test_crm_users():
    """测试用户列表"""
    print("\n" + "="*50)
    print("6. 测试用户列表接口")
    print("="*50)
    
    async with httpx.AsyncClient() as client:
        response = await client.get(f"{BASE_URL}/api/v1/crm/users")
        
    print(f"状态码: {response.status_code}")
    if response.status_code == 200:
        print(f"用户数量: {len(response.json())}")
    return response.status_code == 200


async def run_all_tests():
    """运行所有测试"""
    print("="*60)
    print("🎤 小智语音交互服务 - 功能测试")
    print("="*60)
    
    results = []
    
    # 测试各个接口
    tests = [
        ("健康检查", test_health),
        ("提供商列表", test_providers),
        ("音色列表", test_voices),
        ("文本对话", test_text_chat),
        ("CRM 统计", test_crm_stats),
        ("用户列表", test_crm_users),
    ]
    
    for name, test_func in tests:
        try:
            result = await test_func()
            results.append((name, result))
        except Exception as e:
            print(f"❌ 测试失败: {e}")
            results.append((name, False))
    
    # 打印总结
    print("\n" + "="*60)
    print("📊 测试结果总结")
    print("="*60)
    
    passed = sum(1 for _, result in results if result)
    failed = len(results) - passed
    
    for name, result in results:
        status = "✅ 通过" if result else "❌ 失败"
        print(f"{name}: {status}")
    
    print(f"\n总计: {len(results)} 个测试")
    print(f"通过: {passed} 个")
    print(f"失败: {failed} 个")
    
    return failed == 0


if __name__ == "__main__":
    print("请确保后端服务已启动: python main.py")
    print("按 Enter 开始测试...")
    input()
    
    success = asyncio.run(run_all_tests())
    
    if success:
        print("\n✅ 所有测试通过！")
    else:
        print("\n❌ 部分测试失败，请检查服务状态")
