"""
AI 搞笑分析服务
使用 Deep Seek API 进行多维度搞笑程度分析
"""

import logging
import base64
from pathlib import Path
from typing import Optional, List
from dataclasses import dataclass

from openai import OpenAI

from src.core import get_config


logger = logging.getLogger(__name__)


@dataclass
class HumorScore:
    """
    搞笑评分结果
    """
    humor_score: float = 0.0
    visual_score: float = 0.0
    audio_score: float = 0.0
    text_score: float = 0.0
    humor_level: str = "unknown"
    summary: str = ""
    funny_elements: List[str] = None
    
    def __post_init__(self):
        if self.funny_elements is None:
            self.funny_elements = []
        
        # 根据搞笑分数确定等级
        if self.humor_score >= 80:
            self.humor_level = "非常好笑"
        elif self.humor_score >= 60:
            self.humor_level = "比较搞笑"
        elif self.humor_score >= 40:
            self.humor_level = "一般"
        elif self.humor_score >= 20:
            self.humor_level = "不太搞笑"
        else:
            self.humor_level = "不好笑"


class AIAnalysisError(Exception):
    """AI分析错误"""
    pass


class HumorAnalyzer:
    """
    搞笑程度分析器
    使用 Deep Seek API 进行多模态分析
    """
    
    def __init__(self):
        self.config = get_config().deepseek
        self.analysis_config = get_config().ai_analysis
        
        # 初始化 Deep Seek 客户端
        self.client = OpenAI(
            api_key=self.config.api_key,
            base_url=self.config.base_url,
        )
    
    def analyze_text_humor(self, text: str) -> float:
        """
        分析文字幽默程度
        
        Args:
            text: 待分析的文本（可以是标题、字幕、评论等）
            
        Returns:
            float: 幽默分数（0-100）
        """
        prompt = f"""你是一个专业的幽默评分专家。请分析以下内容的搞笑程度。

评分标准：
- 0-20分：完全不搞笑，内容平淡无奇
- 20-40分：略微有趣，但缺乏幽默感
- 40-60分：有一定搞笑元素，但不突出
- 60-80分：比较搞笑，能让人发笑
- 80-100分：非常搞笑，笑点密集，创意十足

请分析以下内容并给出0-100的分数，只需返回一个数字，不要其他内容：

{text[:500]}
"""
        
        try:
            response = self.client.chat.completions.create(
                model=self.config.model,
                messages=[
                    {"role": "system", "content": "你是一个专业的幽默评分专家。"},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.3,
                max_tokens=10,
            )
            
            score_text = response.choices[0].message.content.strip()
            
            # 尝试提取数字
            import re
            numbers = re.findall(r'\d+', score_text)
            if numbers:
                score = min(100, max(0, int(numbers[0])))
                return float(score)
            
            return 50.0
            
        except Exception as e:
            logger.error(f"文字幽默分析失败: {e}")
            return 50.0
    
    def analyze_video_humor(
        self,
        title: str,
        description: str = "",
        subtitles: Optional[List[str]] = None,
        comments: Optional[List[str]] = None,
        danmu: Optional[List[str]] = None,
    ) -> HumorScore:
        """
        综合分析视频搞笑程度
        
        Args:
            title: 视频标题
            description: 视频描述
            subtitles: 字幕列表
            comments: 评论列表
            danmu: 弹幕列表
            
        Returns:
            HumorScore: 搞笑评分结果
        """
        weights = self.analysis_config.weights
        
        # 1. 分析标题幽默度
        title_score = self.analyze_text_humor(title)
        
        # 2. 分析描述幽默度
        desc_score = 50.0
        if description:
            desc_score = self.analyze_text_humor(description)
        
        # 3. 分析字幕幽默度
        subtitle_score = 50.0
        if subtitles:
            subtitle_text = " ".join(subtitles[:20])
            subtitle_score = self.analyze_text_humor(subtitle_text)
        
        # 4. 分析评论幽默度
        comment_score = 50.0
        if comments:
            comment_text = " ".join([c for c in comments[:10] if isinstance(c, str)])
            comment_score = self.analyze_text_humor(comment_text)
        
        # 5. 分析弹幕幽默度
        danmu_score = 50.0
        if danmu:
            danmu_text = " ".join([d for d in danmu[:20] if isinstance(d, str)])
            danmu_score = self.analyze_text_humor(danmu_text)
        
        # 综合文字评分（标题权重最高）
        text_score = (
            title_score * 0.4 +
            desc_score * 0.1 +
            subtitle_score * 0.2 +
            comment_score * 0.2 +
            danmu_score * 0.1
        )
        
        # 由于没有实际视觉和音频分析，用文字评分模拟
        # 实际项目中可以接入视觉模型和音频模型
        visual_score = text_score * 0.9
        audio_score = text_score * 0.8
        
        # 综合搞笑评分
        humor_score = (
            visual_score * weights["visual"] +
            audio_score * weights["audio"] +
            text_score * weights["text"]
        )
        
        # 生成搞笑元素识别
        funny_elements = self._identify_funny_elements(
            title, subtitles, comments, danmu
        )
        
        # 生成分析总结
        summary = self._generate_summary(
            title_score, desc_score, subtitle_score,
            comment_score, danmu_score, humor_score
        )
        
        return HumorScore(
            humor_score=round(humor_score, 2),
            visual_score=round(visual_score, 2),
            audio_score=round(audio_score, 2),
            text_score=round(text_score, 2),
            summary=summary,
            funny_elements=funny_elements,
        )
    
    def _identify_funny_elements(
        self,
        title: str,
        subtitles: Optional[List[str]] = None,
        comments: Optional[List[str]] = None,
        danmu: Optional[List[str]] = None,
    ) -> List[str]:
        """
        识别搞笑元素
        
        Args:
            title: 标题
            subtitles: 字幕
            comments: 评论
            danmu: 弹幕
            
        Returns:
            List[str]: 搞笑元素列表
        """
        prompt = f"""你是一个搞笑内容分析师。请识别以下内容中包含的搞笑元素。

搞笑元素类型包括：
- 反转：出人意料的剧情或结局
- 夸张：过度夸张的表情、动作、描述
- 谐音：利用谐音制造笑点
- 方言：方言土语带来的喜感
- 吐槽：对事物进行有趣批评
- 模仿：模仿他人或事物的搞笑表演
- 意外：意外事件带来的喜剧效果
- 自嘲：用自我贬低制造笑点

请分析以下内容，列出识别到的搞笑元素（最多5个）：

标题：{title[:100]}
"""
        
        if subtitles:
            prompt += f"\n字幕片段：{' '.join(subtitles[:5])}"
        if comments:
            prompt += f"\n评论：{' '.join(comments[:5])}"
        if danmu:
            prompt += f"\n弹幕：{' '.join(danmu[:5])}"
        
        prompt += "\n\n请用JSON格式返回，格式如下：{\"elements\": [\"元素1\", \"元素2\", ...]}"
        
        try:
            response = self.client.chat.completions.create(
                model=self.config.model,
                messages=[
                    {"role": "system", "content": "你是一个专业的搞笑内容分析师，擅长识别各种搞笑元素。"},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.5,
                max_tokens=500,
            )
            
            import re
            import json
            
            content = response.choices[0].message.content
            
            # 尝试解析 JSON
            json_match = re.search(r'\{.*\}', content, re.DOTALL)
            if json_match:
                data = json.loads(json_match.group())
                return data.get("elements", [])
            
            return []
            
        except Exception as e:
            logger.error(f"搞笑元素识别失败: {e}")
            return []
    
    def _generate_summary(
        self,
        title_score: float,
        desc_score: float,
        subtitle_score: float,
        comment_score: float,
        danmu_score: float,
        humor_score: float,
    ) -> str:
        """
        生成分析总结
        
        Args:
            各维度评分
            
        Returns:
            str: 分析总结
        """
        prompt = f"""请为以下视频搞笑分析生成一段简短的总结（50字以内）：

- 标题得分：{title_score:.0f}/100
- 描述得分：{desc_score:.0f}/100
- 字幕得分：{subtitle_score:.0f}/100
- 评论得分：{comment_score:.0f}/100
- 弹幕得分：{danmu_score:.0f}/100
- 综合得分：{humor_score:.0f}/100

总结："""
        
        try:
            response = self.client.chat.completions.create(
                model=self.config.model,
                messages=[
                    {"role": "system", "content": "你是一个专业的幽默分析师。"},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.5,
                max_tokens=100,
            )
            
            summary = response.choices[0].message.content.strip()
            return summary
            
        except Exception as e:
            logger.error(f"生成总结失败: {e}")
            return f"综合搞笑评分{humor_score:.0f}分，整体{'比较搞笑' if humor_score >= 60 else '一般好笑'}。"
    
    def analyze_images_for_humor(self, image_paths: List[str]) -> float:
        """
        分析图片搞笑程度（可选功能，需要视觉模型）
        
        Args:
            image_paths: 图片路径列表
            
        Returns:
            float: 搞笑分数
        """
        # 此功能需要 GPT-4V 或其他视觉模型
        # 目前先用文字评分模拟
        logger.info("图片分析功能暂未实现，使用默认分数")
        return 50.0


def get_humor_analyzer() -> HumorAnalyzer:
    """
    获取搞笑分析器实例
    
    Returns:
        HumorAnalyzer: 搞笑分析器实例
    """
    return HumorAnalyzer()
