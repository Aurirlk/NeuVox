"""
压力测试配置
使用 Locust 进行并发测试

使用方法:
1. 安装 locust: pip install locust
2. 启动服务: python main.py
3. 启动压测: locust -f tests/locustfile.py --host=http://localhost:8000
4. 访问 Web UI: http://localhost:8089
"""
from locust import HttpUser, task, between


class XiaozhiUser(HttpUser):
    """模拟用户行为"""
    
    # 用户思考时间（秒）
    wait_time = between(1, 3)
    
    def on_start(self):
        """用户启动时"""
        # 健康检查
        self.client.get("/api/v1/health")
    
    @task(5)
    def text_chat(self):
        """文本对话（权重 5）"""
        self.client.post(
            "/api/v1/chat/text",
            json={
                "message": "你好，今天天气怎么样？",
                "history": []
            }
        )
    
    @task(3)
    def get_voices(self):
        """获取音色列表（权重 3）"""
        self.client.get("/api/v1/voices")
    
    @task(2)
    def get_providers(self):
        """获取提供商列表（权重 2）"""
        self.client.get("/api/v1/providers")
    
    @task(2)
    def health_check(self):
        """健康检查（权重 2）"""
        self.client.get("/api/v1/health")
    
    @task(1)
    def crm_stats(self):
        """CRM 统计（权重 1）"""
        self.client.get("/api/v1/crm/stats")
