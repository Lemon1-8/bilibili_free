"""
B站爬虫服务
负责B站视频信息获取、下载、弹幕和评论抓取
"""

import re
import hashlib
import logging
from typing import Optional
from pathlib import Path
from urllib.parse import urlparse

import httpx
import xml.etree.ElementTree as ET

from src.core import get_config


logger = logging.getLogger(__name__)


class BilibiliParseError(Exception):
    """B站URL解析错误"""
    pass


class BilibiliCrawler:
    """
    B站爬虫类
    
    支持解析的URL格式：
    - https://www.bilibili.com/video/BV1xx411c7mD
    - https://www.bilibili.com/video/av170001
    - https://b23.tv/xxxxxx (短链)
    """
    
    # B站域名列表
    BILIBILI_DOMAINS = ["bilibili.com", "b23.tv"]
    
    # 正则匹配模式
    BV_PATTERN = re.compile(r'BV[a-zA-Z0-9]+')
    AV_PATTERN = re.compile(r'av\d+', re.IGNORECASE)
    EP_PATTERN = re.compile(r'ep\d+')
    SS_PATTERN = re.compile(r'ss\d+')
    
    def __init__(self):
        self.config = get_config().bilibili
        self.client = httpx.Client(
            timeout=self.config.timeout,
            headers={
                "User-Agent": self.config.user_agent,
                "Referer": self.config.headers["referer"],
            }
        )
    
    def parse_url(self, url: str) -> dict:
        """
        解析B站URL，获取视频信息
        
        Args:
            url: B站视频URL
            
        Returns:
            dict: 包含 bvid, title, aid 等信息
            
        Raises:
            BilibiliParseError: URL解析失败
        """
        parsed = urlparse(url)
        path = parsed.path
        
        # 短链接处理
        if parsed.netloc == "b23.tv":
            url = self._resolve_short_url(url)
            if not url:
                raise BilibiliParseError("短链接解析失败")
            parsed = urlparse(url)
            path = parsed.path
        
        # 匹配 BV 号
        bv_match = self.BV_PATTERN.search(path)
        if bv_match:
            bvid = bv_match.group()
            return self._get_video_info(bvid)
        
        # 匹配 AV 号
        av_match = self.AV_PATTERN.search(path)
        if av_match:
            avid = int(re.sub(r'av', '', av_match.group(), flags=re.IGNORECASE))
            return self._get_video_info_by_aid(avid)
        
        # 匹配番剧 ep/ss
        ep_match = self.EP_PATTERN.search(path)
        if ep_match:
            epid = ep_match.group()
            return self._get_episode_info(epid)
        
        ss_match = self.SS_PATTERN.search(path)
        if ss_match:
            ssid = ss_match.group()
            return self._get_season_info(ssid)
        
        raise BilibiliParseError(f"无法解析的B站URL: {url}")
    
    def _resolve_short_url(self, short_url: str) -> Optional[str]:
        """
        解析短链接
        
        Args:
            short_url: 短链接
            
        Returns:
            str: 解析后的真实URL
        """
        try:
            response = self.client.head(short_url, allow_redirects=True)
            return str(response.url)
        except Exception as e:
            logger.error(f"短链接解析失败: {e}")
            return None
    
    def _get_video_info(self, bvid: str) -> dict:
        """
        通过BV号获取视频信息
        
        Args:
            bvid: BV号
            
        Returns:
            dict: 视频信息
        """
        api_url = f"https://api.bilibili.com/x/web-interface/view?bvid={bvid}"
        
        response = self.client.get(api_url)
        response.raise_for_status()
        
        data = response.json()
        
        if data["code"] != 0:
            raise BilibiliParseError(f"API返回错误: {data.get('message', '未知错误')}")
        
        result = data["data"]
        
        return {
            "bvid": result["bvid"],
            "aid": result["aid"],
            "title": result["title"],
            "description": result["desc"],
            "duration": result["duration"],
            "owner": result["owner"]["name"],
            "tname": result["tname"],
            "pic": result["pic"],
            "cid": result["cid"],
            "dimension": result["dimension"],
        }
    
    def _get_video_info_by_aid(self, aid: int) -> dict:
        """
        通过AV号获取视频信息
        
        Args:
            aid: AV号
            
        Returns:
            dict: 视频信息
        """
        api_url = f"https://api.bilibili.com/x/web-interface/view?aid={aid}"
        
        response = self.client.get(api_url)
        response.raise_for_status()
        
        data = response.json()
        
        if data["code"] != 0:
            raise BilibiliParseError(f"API返回错误: {data.get('message', 'Unknown error')}")
        
        result = data["data"]
        
        return {
            "bvid": result["bvid"],
            "aid": result["aid"],
            "title": result["title"],
            "description": result["desc"],
            "duration": result["duration"],
            "owner": result["owner"]["name"],
            "tname": result["tname"],
            "pic": result["pic"],
            "cid": result["cid"],
        }
    
    def _get_episode_info(self, epid: str) -> dict:
        """
        获取番剧剧集信息
        
        Args:
            epid: EP ID
            
        Returns:
            dict: 剧集信息
        """
        api_url = f"https://api.bilibili.com/pugv/view/web/season?ep_id={epid.replace('ep', '')}"
        
        response = self.client.get(api_url)
        response.raise_for_status()
        
        data = response.json()
        
        if data["code"] != 0:
            raise BilibiliParseError(f"API返回错误: {data.get('message', 'Unknown error')}")
        
        result = data["data"]["episode"]
        
        return {
            "epid": epid,
            "aid": result["aid"],
            "title": result["title"],
            "long_title": result["long_title"],
            "cid": result["cid"],
        }
    
    def _get_season_info(self, ssid: str) -> dict:
        """
        获取番剧季度信息
        
        Args:
            ssid: SS ID
            
        Returns:
            dict: 季度信息
        """
        api_url = f"https://api.bilibili.com/pugv/view/web/season?ss_id={ssid.replace('ss', '')}"
        
        response = self.client.get(api_url)
        response.raise_for_status()
        
        data = response.json()
        
        if data["code"] != 0:
            raise BilibiliParseError(f"API返回错误: {data.get('message', 'Unknown error')}")
        
        result = data["data"]
        episodes = []
        
        for ep in result["episodes"]:
            episodes.append({
                "epid": f"ep{ep['ep_id']}",
                "aid": ep["aid"],
                "title": ep["title"],
                "long_title": ep.get("long_title", ""),
                "cid": ep["cid"],
            })
        
        return {
            "ssid": ssid,
            "title": result["title"],
            "episodes": episodes,
        }
    
    def get_danmu(self, cid: int) -> list:
        """
        获取弹幕列表
        
        Args:
            cid: 视频CID
            
        Returns:
            list: 弹幕列表，每条弹幕包含 dmid, text, time 等
        """
        api_url = f"https://api.bilibili.com/x/v1/dm/list.so?oid={cid}"
        
        response = self.client.get(api_url)
        response.raise_for_status()
        
        danmu_list = []
        
        try:
            root = ET.fromstring(response.content)
            
            for d_element in root.iter("d"):
                danmu = {
                    "dmid": d_element.get("dmid", ""),
                    "text": d_element.text or "",
                    "time": float(d_element.get("p", "0").split(",")[0]),
                }
                danmu_list.append(danmu)
                
        except ET.ParseError as e:
            logger.error(f"弹幕XML解析失败: {e}")
        
        return danmu_list
    
    def get_comments(
        self,
        oid: int,
        page: int = 1,
        page_size: int = 20,
        cookies: dict = None,
        sort: int = 2,
    ) -> dict:
        """
        获取视频评论

        Args:
            oid: 视频 aid
            page: 页码
            page_size: 每页数量
            cookies: 登录Cookie字典
            sort: 排序方式（0推荐 1最新 2热评，默认2热评）

        Returns:
            dict: 包含评论列表和分页信息
        """
        headers = {
            "Referer": "https://www.bilibili.com",
            "User-Agent": self.config.user_agent,
        }

        if cookies:
            cookie_str = "; ".join([f"{k}={v}" for k, v in cookies.items()])
            headers["Cookie"] = cookie_str

        api_url = f"https://api.bilibili.com/x/v2/reply?type=1&oid={oid}&pn={page}&ps={page_size}&sort={sort}"

        response = self.client.get(api_url, headers=headers)
        response.raise_for_status()

        data = response.json()

        if data["code"] != 0:
            logger.warning(f"评论API返回错误: {data.get('message', 'Unknown error')}")
            return {"replies": [], "count": 0, "page": page}

        result = data["data"]

        if result is None:
            return {"replies": [], "count": 0, "page": page}

        comments = []
        for reply in result.get("replies") or []:
            comments.append({
                "rpid": reply["rpid"],
                "oid": reply["oid"],
                "type": reply["type"],
                "mid": reply["mid"],
                "uname": reply["member"]["uname"],
                "content": reply["content"]["message"],
                "like": reply["like"],
                "ctime": reply["ctime"],
                "rcount": reply["rcount"],
                "replies": reply.get("replies") or [],
            })

        return {
            "replies": comments,
            "count": result.get("cursor", {}).get("total", 0),
            "page": page,
            "page_size": page_size,
        }

    def get_all_comments(
        self,
        oid: int,
        max_pages: int = 50,
        cookies: dict = None,
        sort: int = 5,
    ) -> list:
        """
        获取所有评论（分页）

        Args:
            oid: 视频 aid
            max_pages: 最大页数限制
            cookies: 登录Cookie字典
            sort: 排序方式（0推荐 1最新 2热评，默认2热评）

        Returns:
            list: 所有评论列表
        """
        all_comments = []

        for page in range(1, max_pages + 1):
            result = self.get_comments(oid, page=page, cookies=cookies, sort=sort)
            comments = result["replies"]

            if not comments:
                break

            all_comments.extend(comments)

            if len(comments) < result["page_size"]:
                break

        return all_comments
    
    def download_video(
        self,
        bvid: str,
        save_path: str,
        cid: int = None,
        quality: int = 80,
        cookies: dict = None,
    ) -> str:
        """
        下载视频

        Args:
            bvid: BV号
            save_path: 保存路径
            cid: 视频CID（如果为None则自动获取）
            quality: 画质等级（默认80为高清）
            cookies: 登录Cookie字典，如 {"SESSDATA": "xxx", "bili_jct": "xxx"}

        Returns:
            str: 保存的文件路径
        """
        # 如果没有提供CID，获取视频信息以获取CID
        if cid is None:
            video_info = self._get_video_info(bvid)
            cid = video_info.get("cid")

        if cid is None:
            raise BilibiliParseError("无法获取视频CID")

        # 构建请求头
        headers = {
            "Referer": "https://www.bilibili.com",
            "User-Agent": self.config.user_agent,
        }

        # 如果提供了cookies，添加到请求头
        if cookies:
            cookie_str = "; ".join([f"{k}={v}" for k, v in cookies.items()])
            headers["Cookie"] = cookie_str

        # 获取下载链接
        playurl_api = f"https://api.bilibili.com/x/player/playurl?bvid={bvid}&cid={cid}&qn={quality}&fnval=0"

        response = self.client.get(playurl_api, headers=headers)
        response.raise_for_status()

        data = response.json()

        if data["code"] != 0:
            raise BilibiliParseError(f"获取下载链接失败: {data.get('message', '请求错误')}")

        video_url = data["data"]["durl"][0]["url"]

        # 下载视频
        video_response = self.client.get(video_url, headers=headers)

        save_path = Path(save_path)
        save_path.parent.mkdir(parents=True, exist_ok=True)

        with open(save_path, "wb") as f:
            for chunk in video_response.iter_bytes(chunk_size=8192):
                f.write(chunk)

        return str(save_path)
    
    def get_thumbnail(self, pic_url: str, save_path: str) -> str:
        """
        下载视频封面缩略图
        
        Args:
            pic_url: 封面URL
            save_path: 保存路径
            
        Returns:
            str: 保存的文件路径
        """
        response = self.client.get(pic_url)
        response.raise_for_status()
        
        save_path = Path(save_path)
        save_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(save_path, "wb") as f:
            f.write(response.content)
        
        return str(save_path)
    
    def close(self):
        """关闭客户端"""
        self.client.close()


def get_bilibili_crawler() -> BilibiliCrawler:
    """
    获取B站爬虫实例
    
    Returns:
        BilibiliCrawler: B站爬虫实例
    """
    return BilibiliCrawler()
