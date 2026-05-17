"""
知识库查询工具
支持 jieba 分词 + TF-IDF 关键词提取 + 向量语义搜索
"""
import re
from typing import Any, Dict, List

from app.tools.base import BaseTool, ToolResult
from app.utils.logger import logger


class KnowledgeTool(BaseTool):
    """知识库查询工具"""
    
    @property
    def name(self) -> str:
        return "query_knowledge"
    
    @property
    def description(self) -> str:
        return "查询知识库获取专业信息。当用户询问专业领域知识、技术问题、法律问题、或需要从本地知识库检索信息时调用此工具。"
    
    @property
    def schema(self) -> Dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "查询内容"
                        },
                        "context": {
                            "type": "string",
                            "description": "上下文信息"
                        }
                    },
                    "required": ["query"]
                }
            }
        }
    
    async def execute(self, **kwargs) -> ToolResult:
        """执行知识库查询"""
        query = kwargs.get("query", "")
        context = kwargs.get("context", "")
        
        if not query:
            return ToolResult(
                success=False,
                data=None,
                error="查询内容不能为空",
                tool_name=self.name
            )
        
        try:
            # 1. jieba 分词提取关键词
            keywords = self._extract_keywords_jieba(query)
            logger.info(f"[KnowledgeTool] jieba 提取关键词: {keywords}")
            
            # 2. 在本地知识库中搜索
            from app.knowledge.rag_service import rag_service
            await rag_service.load_knowledge_base()
            
            # 使用关键词搜索
            search_query = " ".join(keywords) if keywords else query
            search_results = await rag_service.search(search_query, limit=3)
            
            # 如果关键词搜索无结果，用原始查询搜索
            if not search_results:
                search_results = await rag_service.search(query, limit=3)
            
            if not search_results:
                return ToolResult(
                    success=True,
                    data={"response": "未在知识库中找到相关信息", "keywords": keywords},
                    tool_name=self.name
                )
            
            # 3. 拼接搜索结果
            context_parts = []
            for i, result in enumerate(search_results, 1):
                source = result.get("source", result.get("metadata", {}).get("source", "未知"))
                content = result.get("content", "")
                score = result.get("distance", 0)
                context_parts.append(f"[来源{i}: {source} (相关度: {score:.2f})]\n{content}")
            
            knowledge_context = "\n\n".join(context_parts)
            
            return ToolResult(
                success=True,
                data={
                    "keywords": keywords,
                    "search_results": search_results,
                    "context": knowledge_context
                },
                tool_name=self.name
            )
            
        except Exception as e:
            logger.error(f"[KnowledgeTool] 查询失败: {e}")
            return ToolResult(
                success=False,
                data=None,
                error=str(e),
                tool_name=self.name
            )
    
    def _extract_keywords_jieba(self, text: str) -> List[str]:
        """
        使用 jieba 进行中文分词和关键词提取
        
        Args:
            text: 输入文本
            
        Returns:
            关键词列表
        """
        try:
            import jieba
            import jieba.analyse
            
            # 使用 jieba TF-IDF 提取关键词
            keywords = jieba.analyse.extract_tags(text, topK=5, withWeight=False)
            
            # 如果 TF-IDF 提取失败，使用基本分词
            if not keywords:
                keywords = list(jieba.cut(text))
                # 过滤停用词和短词
                stop_words = {"的", "了", "在", "是", "我", "有", "和", "就", "不", "人",
                              "都", "一", "上", "也", "很", "到", "说", "要", "去", "你",
                              "会", "着", "没有", "看", "好", "这", "那", "吗", "呢", "啊"}
                keywords = [w for w in keywords if w not in stop_words and len(w) > 1]
            
            return keywords[:5]  # 最多返回5个关键词
            
        except ImportError:
            logger.warning("[KnowledgeTool] jieba 未安装，使用简单分词")
            return self._simple_tokenize(text)
        except Exception as e:
            logger.error(f"[KnowledgeTool] jieba 分词失败: {e}")
            return self._simple_tokenize(text)
    
    def _simple_tokenize(self, text: str) -> List[str]:
        """简单分词（降级方案）"""
        stop_words = {"的", "了", "在", "是", "我", "有", "和", "就", "不", "人",
                      "都", "一", "上", "也", "很", "到", "说", "要", "去", "你",
                      "会", "着", "没有", "看", "好", "这", "那", "吗", "呢", "啊"}
        
        text = re.sub(r'[，。！？、；：""''（）\[\]【】]', ' ', text)
        words = text.split()
        keywords = [w for w in words if w not in stop_words and len(w) > 1]
        
        return keywords[:5]
    
    def _tfidf_keywords(self, texts: List[str], top_k: int = 5) -> List[str]:
        """
        使用 TF-IDF 提取关键词
        
        Args:
            texts: 文档列表
            top_k: 返回前k个关键词
            
        Returns:
            关键词列表
        """
        try:
            from sklearn.feature_extraction.text import TfidfVectorizer
            import jieba
            
            # 使用 jieba 分词
            segmented_texts = [" ".join(jieba.cut(text)) for text in texts]
            
            # TF-IDF 向量化
            vectorizer = TfidfVectorizer(max_features=100)
            tfidf_matrix = vectorizer.fit_transform(segmented_texts)
            
            # 获取特征名（关键词）
            feature_names = vectorizer.get_feature_names_out()
            
            # 获取平均 TF-IDF 分数
            mean_tfidf = tfidf_matrix.mean(axis=0).A1
            
            # 获取 Top-K 关键词
            top_indices = mean_tfidf.argsort()[-top_k:][::-1]
            keywords = [feature_names[i] for i in top_indices]
            
            return keywords
            
        except ImportError:
            logger.warning("[KnowledgeTool] scikit-learn 未安装")
            return []
        except Exception as e:
            logger.error(f"[KnowledgeTool] TF-IDF 提取失败: {e}")
            return []
    
    async def search_with_web_fallback(self, query: str) -> ToolResult:
        """
        知识库搜索 + 联网搜索降级
        """
        result = await self.execute(query=query)
        
        if result.success and result.data.get("search_results"):
            return result
        
        # 降级到联网搜索
        logger.info("[KnowledgeTool] 本地知识库无结果，降级到联网搜索")
        
        try:
            from app.tools.search_tool import SearchTool
            search_tool = SearchTool()
            web_result = await search_tool.execute(query=query, max_results=3)
            
            if web_result.success:
                return ToolResult(
                    success=True,
                    data={
                        "keywords": result.data.get("keywords", []) if result.data else [],
                        "search_results": web_result.data.get("search_results", []),
                        "context": "来自网络搜索的结果",
                        "source": "web_search"
                    },
                    tool_name=self.name
                )
        except Exception as e:
            logger.error(f"[KnowledgeTool] 联网搜索降级失败: {e}")
        
        return result
