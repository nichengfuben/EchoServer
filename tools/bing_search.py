import requests
from bs4 import BeautifulSoup
import json
import re
from urllib.parse import quote, unquote
from datetime import datetime
import time


class BingSearcher:
    def __init__(self):
        """
        初始化一个搜索引擎对象，用来模拟浏览器访问Bing。
        设置好默认的请求头，让Bing以为你是用浏览器访问的。
        """
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
            'Accept-Encoding': 'gzip, deflate, br',
            'DNT': '1',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none',
            'Sec-Fetch-User': '?1',
            'Cache-Control': 'max-age=0'
        })

    def search(self, keyword, page=1):
        """
        根据关键词和页码，向Bing发送搜索请求并返回结果。

        参数:
            keyword (str): 搜索关键词
            page (int): 第几页（从1开始）

        返回:
            dict: 结构化的搜索结果，模仿Bing API格式
        """
        # 每页10条结果，计算起始位置
        first = (page - 1) * 10

        # 构造搜索URL
        base_url = "https://cn.bing.com/search"
        params = {
            'q': keyword,
            'first': first,
            'PC': 'U531',
            'FORM': 'PERE' if page > 1 else 'QBRE'
        }

        try:
            # 发送GET请求
            response = self.session.get(base_url, params=params, timeout=10)
            response.raise_for_status()

            # 处理编码问题，避免乱码
            if response.encoding is None or response.encoding == 'ISO-8859-1':
                response.encoding = response.apparent_encoding or 'utf-8'

            # 获取HTML内容
            html_content = response.text
            # 如果发现乱码，尝试不同编码方式
            if ' ' in html_content or html_content.count('\\x') > 5:
                try:
                    html_content = response.content.decode('utf-8', errors='ignore')
                except:
                    try:
                        html_content = response.content.decode('gbk', errors='ignore')
                    except:
                        html_content = response.content.decode('utf-8', errors='replace')

            # 使用BeautifulSoup解析HTML
            soup = BeautifulSoup(html_content, 'html.parser')

            # 把解析结果整理成标准格式
            result = self._build_json_response(soup, keyword, page, response.url)

            return result

        except requests.RequestException as e:
            # 请求出错时返回错误信息
            return {
                "_type": "SearchResponse",
                "error": {
                    "code": "RequestError",
                    "message": str(e),
                    "moreDetails": "网络请求失败"
                }
            }
        except Exception as e:
            # 解析出错时返回错误信息
            return {
                "_type": "SearchResponse",
                "error": {
                    "code": "ParseError",
                    "message": str(e),
                    "moreDetails": "解析失败"
                }
            }

    def _build_json_response(self, soup, keyword, page, search_url):
        """
        把BeautifulSoup解析出来的数据，整理成统一的JSON结构。
        """
        # 获取总搜索数量（大概）
        total_results = self._extract_total_results(soup)

        # 初始化返回的数据结构
        response = {
            "_type": "SearchResponse",
            "queryContext": {
                "originalQuery": keyword,
                "currentPage": page,
                "askUserForLocation": False
            },
            "webPages": {
                "webSearchUrl": search_url,
                "totalEstimatedMatches": total_results,
                "value": [],
                "someResultsRemoved": False
            },
            "rankingResponse": {
                "mainline": {
                    "items": []
                },
                "sidebar": {
                    "items": []
                }
            }
        }

        # 提取特色答案（比如百科类）
        self._extract_top_answers(soup, response)

        # 提取网页搜索结果
        self._extract_web_results(soup, response)

        # 提取视频结果
        self._extract_video_results(soup, response)

        # 提取图片结果
        self._extract_image_results(soup, response)

        # 提取相关搜索建议
        self._extract_related_searches(soup, response)

        # 提取侧边栏内容（比如知识图谱）
        self._extract_sidebar_content(soup, response)

        return response

    def _extract_total_results(self, soup):
        """
        估算总共的搜索结果数。
        """
        results_container = soup.find('ol', id='b_results')
        if results_container:
            items = results_container.find_all('li', class_='b_algo')
            return len(items) * 100000 if items else 0
        return 0

    def _extract_top_answers(self, soup, response):
        """
        提取Bing顶部的特色答案（例如百科、知识类信息）。
        """
        top_container = soup.find('ol', id='b_topw')
        if not top_container:
            return

        top_answers = top_container.find_all('li', class_='b_ans')

        for answer in top_answers:
            answer_data = {
                "answerType": "FeaturedSnippet",
                "resultIndex": 0,
                "value": {}
            }

            # 标题和链接
            title_elem = answer.find('h2')
            if title_elem:
                link = title_elem.find('a')
                if link:
                    answer_data["value"]["name"] = self._clean_text(link.get_text())
                    answer_data["value"]["url"] = link.get('href', '')

            # 内容摘要
            content_elem = answer.find('div', class_='b_caption') or answer.find('p')
            if content_elem:
                answer_data["value"]["snippet"] = self._clean_text(content_elem.get_text())

            # 来源地址
            cite_elem = answer.find('cite')
            if cite_elem:
                answer_data["value"]["displayUrl"] = self._clean_text(cite_elem.get_text())

            if answer_data["value"]:
                response["rankingResponse"]["mainline"]["items"].insert(0, answer_data)

    def _extract_web_results(self, soup, response):
        """
        提取网页搜索结果列表。
        """
        main_results = soup.find('ol', id='b_results')
        if not main_results:
            return

        search_items = main_results.find_all('li', class_='b_algo')

        for index, item in enumerate(search_items):
            result = {
                "id": f"https://api.cognitive.microsoft.com/api/v7/#WebPages.{index}",
                "name": "",
                "url": "",
                "isFamilyFriendly": True,
                "displayUrl": "",
                "snippet": "",
                "dateLastCrawled": datetime.now().isoformat() + "Z",
                "language": "zh-CN",
                "isNavigational": False
            }

            # 标题和链接
            title_elem = item.find('h2')
            if title_elem:
                link = title_elem.find('a')
                if link:
                    result["name"] = self._clean_text(link.get_text())
                    result["url"] = link.get('href', '')
                    if 'tilk' in link.get('class', []):
                        result["isNavigational"] = True

            # 网站名称
            site_info = item.find('div', class_='b_tpcn')
            if site_info:
                site_name = site_info.find('div', class_='tptt')
                if site_name:
                    result["siteName"] = self._clean_text(site_name.get_text())

            # 显示URL
            cite_elem = item.find('cite')
            if cite_elem:
                result["displayUrl"] = self._clean_text(cite_elem.get_text())

            # 摘要
            caption = item.find('div', class_='b_caption')
            if caption:
                snippet_elem = caption.find('p')
                if snippet_elem:
                    result["snippet"] = self._clean_text(snippet_elem.get_text())
                else:
                    result["snippet"] = self._clean_text(caption.get_text())

            # 发布时间
            if result["snippet"]:
                date_patterns = [
                    r'(\d{4}年\d{1,2}月\d{1,2}日)',
                    r'(\d{1,2}天前)',
                    r'(\d{1,2}小时前)'
                ]
                for pattern in date_patterns:
                    date_match = re.search(pattern, result["snippet"])
                    if date_match:
                        result["datePublished"] = date_match.group(1)
                        break

            # 深层链接（子页面）
            deeplinks = []
            deeplink_container = item.find('div', class_='b_vlist2col')
            if deeplink_container:
                for link in deeplink_container.find_all('a'):
                    deeplink = {
                        "name": self._clean_text(link.get_text()),
                        "url": link.get('href', '')
                    }
                    if deeplink["name"] and deeplink["url"]:
                        deeplinks.append(deeplink)

            vlist = item.find('ul', class_='b_vList')
            if vlist:
                for li in vlist.find_all('li'):
                    link = li.find('a')
                    if link:
                        deeplink = {
                            "name": self._clean_text(link.get_text()),
                            "url": link.get('href', '')
                        }
                        if deeplink["name"] and deeplink["url"]:
                            deeplinks.append(deeplink)

            if deeplinks:
                result["deepLinks"] = deeplinks

            # 富卡片（比如百科）
            rich_card = item.find('div', class_='b_richcard')
            if rich_card:
                result["richFacts"] = self._extract_rich_card_data(rich_card)

            # 图片
            images = self._extract_result_images(item)
            if images:
                result["images"] = images

            # 只添加有效结果
            if result["url"]:
                response["webPages"]["value"].append(result)

                # 加入排名列表
                response["rankingResponse"]["mainline"]["items"].append({
                    "answerType": "WebPages",
                    "resultIndex": index,
                    "value": {
                        "id": result["id"]
                    }
                })

    def _extract_rich_card_data(self, rich_card):
        """
        提取富卡片信息（比如百科标签页内容）。
        """
        facts = []

        tab_container = rich_card.find('div', class_='tab-container')
        if tab_container:
            tabs = tab_container.find_all('li', role='tab')
            for tab in tabs:
                tab_name = self._clean_text(tab.get_text())
                if tab_name:
                    facts.append({
                        "label": tab_name,
                        "value": "",
                        "type": "tab"
                    })

        tab_content = rich_card.find('div', class_='tab-content')
        if tab_content:
            active_tab = tab_content.find('div', {'role': 'tabpanel'})
            if active_tab and not active_tab.get('class', [''])[0].endswith('hide'):
                content_text = self._clean_text(active_tab.get_text())
                if content_text and facts:
                    facts[0]["value"] = content_text + "..." if len(content_text) > 200 else content_text

        return facts if facts else None

    def _extract_result_images(self, item):
        """
        提取搜索结果中的图片。
        """
        images = []

        img_set = item.find('div', class_='b_imgSet')
        if img_set:
            for img_link in img_set.find_all('a'):
                img_div = img_link.find('div', class_='rms_iac')
                if img_div:
                    img_url = img_div.get('data-src', '')
                    if img_url:
                        images.append({
                            "thumbnailUrl": img_url,
                            "hostPageUrl": img_link.get('href', '')
                        })

        single_img = item.find('div', class_='b_imagePair')
        if single_img:
            img_div = single_img.find('div', class_='rms_iac')
            if img_div:
                img_url = img_div.get('data-src', '')
                if img_url:
                    images.append({
                        "thumbnailUrl": img_url
                    })

        return images if images else None

    def _extract_video_results(self, soup, response):
        """
        提取视频搜索结果。
        """
        videos = []

        video_containers = soup.find_all('div', class_='mc_vtvc')

        for video in video_containers:
            video_data = {
                "name": "",
                "description": "",
                "webSearchUrl": "",
                "thumbnailUrl": "",
                "datePublished": "",
                "publisher": [],
                "duration": "",
                "viewCount": 0
            }

            link = video.find('a', class_='mc_vtvc_link')
            if link:
                video_data["webSearchUrl"] = link.get('href', '')
                title_elem = video.find('div', class_='mc_vtvc_title')
                if title_elem:
                    video_data["name"] = self._clean_text(title_elem.get_text())

            img = video.find('img', class_='rms_img')
            if img:
                video_data["thumbnailUrl"] = img.get('data-src-hq', '') or img.get('src', '')

            duration_elem = video.find('div', class_='mc_bc_w')
            if duration_elem:
                video_data["duration"] = self._clean_text(duration_elem.get_text())

            source_elem = video.find('span', class_='srcttl')
            if source_elem:
                video_data["publisher"] = [{
                    "name": self._clean_text(source_elem.get_text())
                }]

            channel_elem = video.find('span', class_='mc_vtvc_meta_row_channel')
            if channel_elem:
                video_data["creator"] = {
                    "name": self._clean_text(channel_elem.get_text())
                }

            view_elem = video.find('span', class_='meta_vc_content')
            if view_elem:
                view_text = self._clean_text(view_elem.get_text())
                view_match = re.search(r'(\d+)', view_text.replace(',', ''))
                if view_match:
                    video_data["viewCount"] = int(view_match.group(1))

            date_elem = video.find('span', class_='meta_pd_content')
            if date_elem:
                video_data["datePublished"] = self._clean_text(date_elem.get_text())

            if video_data["webSearchUrl"]:
                videos.append(video_data)

        if videos:
            response["videos"] = {
                "id": "https://api.cognitive.microsoft.com/api/v7/#Videos",
                "readLink": "https://api.cognitive.microsoft.com/api/v7/videos/search?q=" + quote(
                    response["queryContext"]["originalQuery"]),
                "webSearchUrl": f"https://cn.bing.com/videos/search?q={quote(response['queryContext']['originalQuery'])}",
                "isFamilyFriendly": True,
                "value": videos
            }

            # 添加到排名
            response["rankingResponse"]["mainline"]["items"].append({
                "answerType": "Videos",
                "value": {
                    "id": "https://api.cognitive.microsoft.com/api/v7/#Videos"
                }
            })

    def _extract_image_results(self, soup, response):
        """
        提取图片搜索结果。
        """
        images = []

        image_containers = soup.find_all('div', class_='b_imgSet')

        for container in image_containers:
            for img_item in container.find_all('li'):
                img_link = img_item.find('a')
                if img_link:
                    img_data = {
                        "name": img_link.get('title', ''),
                        "webSearchUrl": "",
                        "thumbnailUrl": "",
                        "datePublished": datetime.now().isoformat() + "Z",
                        "contentUrl": "",
                        "hostPageUrl": "",
                        "contentSize": "",
                        "encodingFormat": "jpeg",
                        "width": 0,
                        "height": 0
                    }

                    href = img_link.get('href', '')
                    if href:
                        if href.startswith('/images/'):
                            img_data["webSearchUrl"] = f"https://cn.bing.com{href}"
                        else:
                            img_data["hostPageUrl"] = href

                    img_div = img_link.find('div', class_='rms_iac')
                    if img_div:
                        thumb_url = img_div.get('data-src', '')
                        if thumb_url:
                            img_data["thumbnailUrl"] = thumb_url

                            width = img_div.get('data-width', '0')
                            height = img_div.get('data-height', '0')
                            try:
                                img_data["width"] = int(width) if width else 0
                                img_data["height"] = int(height) if height else 0
                            except:
                                pass

                    if img_data["thumbnailUrl"]:
                        images.append(img_data)

        if images:
            response["images"] = {
                "id": "https://api.cognitive.microsoft.com/api/v7/#Images",
                "readLink": "https://api.cognitive.microsoft.com/api/v7/images/search?q=" + quote(
                    response["queryContext"]["originalQuery"]),
                "webSearchUrl": f"https://cn.bing.com/images/search?q={quote(response['queryContext']['originalQuery'])}",
                "isFamilyFriendly": True,
                "value": images
            }

    def _extract_related_searches(self, soup, response):
        """
        提取相关的搜索建议。
        """
        related = []

        related_containers = [
            soup.find('div', class_='b_rs'),
            soup.find('ul', class_='b_vList'),
            soup.find('div', {'id': 'b_context'})
        ]

        for container in related_containers:
            if container:
                for link in container.find_all('a'):
                    text = self._clean_text(link.get_text())
                    href = link.get('href', '')

                    if text and '/search' in href:
                        query = ""
                        if '?q=' in href:
                            query_match = re.search(r'[?&]q=([^&]+)', href)
                            if query_match:
                                query = unquote(query_match.group(1))

                        related.append({
                            "text": text,
                            "displayText": text,
                            "webSearchUrl": f"https://cn.bing.com/search?q={quote(query or text)}"
                        })

        seen = set()
        unique_related = []
        for item in related:
            if item["text"] not in seen:
                seen.add(item["text"])
                unique_related.append(item)

        if unique_related:
            response["relatedSearches"] = {
                "id": "https://api.cognitive.microsoft.com/api/v7/#RelatedSearches",
                "value": unique_related
            }

    def _extract_sidebar_content(self, soup, response):
        """
        提取侧边栏内容（比如知识图谱）。
        """
        sidebar = soup.find('div', class_='b_entityTP') or soup.find('div', class_='b_sideBleed')

        if sidebar:
            entity_data = {
                "id": "https://api.cognitive.microsoft.com/api/v7/#Entities",
                "value": []
            }

            title = sidebar.find('h2')
            if title:
                entity = {
                    "name": self._clean_text(title.get_text()),
                    "description": "",
                    "webSearchUrl": "",
                    "image": None
                }

                desc = sidebar.find('div', class_='b_entitySubTitle')
                if desc:
                    entity["description"] = self._clean_text(desc.get_text())

                img = sidebar.find('img')
                if img:
                    entity["image"] = {
                        "thumbnailUrl": img.get('src', '') or img.get('data-src', ''),
                        "hostPageUrl": ""
                    }

                entity_data["value"].append(entity)

            if entity_data["value"]:
                response["entities"] = entity_data

                response["rankingResponse"]["sidebar"]["items"].append({
                    "answerType": "Entities",
                    "value": {
                        "id": entity_data["id"]
                    }
                })

    def _clean_text(self, text):
        """
        清理文本中的多余空格和HTML标签。
        """
        if not text:
            return ""

        text = str(text)
        text = re.sub(r'<[^>]+>', '', text)
        text = re.sub(r'\s+', ' ', text)
        text = text.replace('\u200b', '')
        text = text.replace('\xa0', ' ')
        text = text.replace('\u0083', '')
        text = text.strip()

        return text


def search_bing(keyword, page=1):
    """
    便捷函数：搜索Bing并返回结果。
    """
    searcher = BingSearcher()
    return searcher.search(keyword, page)

##print(search_bing("你好"))
