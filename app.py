import datetime
import json
import re
import requests
from bs4 import BeautifulSoup
from jinja2 import Template
import dashscope
from dashscope.api_entities.dashscope_response import HTTPStatus
import streamlit as st
import streamlit.components.v1 as components
from urllib.parse import urljoin
from http import HTTPStatus
st.set_page_config(
    page_title="跨境物流 AI 爆款生成器",
    page_icon="🚀",
    layout="wide"
)

# DEFAULT_API_KEY = "**"
try:
    DEFAULT_API_KEY = st.secrets["DASHSCOPE_API_KEY"]
except:
    DEFAULT_API_KEY = ""
dashscope.api_key = DEFAULT_API_KEY
WRITING_STYLES = [
    "专业深度政策解读 (客观、专业、干货满满)",
    "引发跨境卖家共鸣 (制造危机感、剖析痛点、避免踩坑)",
    "宏观趋势与数据分析 (全局视角、适合高管与货代老板阅读)",
    "突发新闻与紧急应对 (节奏快、提炼重点、直接给出行动指南)",
    "大白话轻松吐槽 (幽默吃瓜风格，把枯燥物流讲成段子)"
]

WECHAT_HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{{ article.title }}</title>
    <style>
        body {
            background-color: #f7f8fa; font-family: -apple-system, BlinkMacSystemFont, "PingFang SC", "Microsoft YaHei", sans-serif;
            margin: 0; padding: 20px 10px; color: #333; line-height: 1.8;
        }
        .container {
            max-width: 100%; margin: 0 auto; background: #ffffff; border-radius: 8px; 
            box-shadow: 0 4px 15px rgba(0,0,0,0.05); padding: 30px 25px; box-sizing: border-box;
        }
        h1 { font-size: 24px; color: #1a202c; margin-bottom: 15px; font-weight: bold; line-height: 1.4; }
        .meta-info { font-size: 14px; color: #718096; margin-bottom: 30px; display: flex; flex-wrap: wrap; gap: 10px; border-bottom: 1px solid #edf2f7; padding-bottom: 15px;}
        .author-tag { color: #3182ce; font-weight: 500; }
        .style-tag { background: #edf2f7; color: #4a5568; padding: 2px 8px; border-radius: 4px; font-size: 12px; }

        .content { margin-top: 20px; }
        .text-p { font-size: 16px; color: #2d3748; margin-bottom: 20px; text-align: justify; }
        .sub-title {
            font-size: 18px; font-weight: bold; color: #2b6cb0; margin: 35px 0 15px 0; display: flex; align-items: center;
            background: #ebf8ff; padding: 8px 15px; border-left: 4px solid #3182ce; border-radius: 0 4px 4px 0;
        }
        .quote-box {
            background-color: #f7fafc; border-left: 4px solid #a0aec0; padding: 15px 20px; margin: 25px 0; font-size: 15px; color: #4a5568; font-style: italic;
        }
        .highlight { color: #e53e3e; font-weight: bold; background: rgba(254, 215, 215, 0.5); padding: 0 2px;}

        .img-container { text-align: center; margin: 25px 0; }
        .img-container img { max-width: 100%; border-radius: 6px; box-shadow: 0 2px 8px rgba(0,0,0,0.1); }
        .img-caption { font-size: 13px; color: #a0aec0; margin-top: 8px; }

        .footer { margin-top: 40px; text-align: center; padding-top: 20px; border-top: 1px dashed #e2e8f0; font-size: 13px; color: #a0aec0;}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>{{ article.title }}</h1>
            <div class="meta-info">
                <span class="author-tag">全球物流前沿</span>
                <span>{{ date }}</span>
                <span class="style-tag">风格: {{ style_name }}</span>
            </div>
        </div>
        <div class="content">
            {% for item in article.blocks %}
                {% if item.type == 'subtitle' %}
                    <div class="sub-title">{{ item.content }}</div>
                {% elif item.type == 'text' %}
                    <div class="text-p">{{ item.content }}</div>
                {% elif item.type == 'quote' %}
                    <div class="quote-box">{{ item.content }}</div>
                {% elif item.type == 'image' %}
                    <div class="img-container">
                        <img src="{{ item.url }}" alt="插图">
                        {% if item.caption %}<div class="img-caption">{{ item.caption }}</div>{% endif %}
                    </div>
                {% endif %}
            {% endfor %}
        </div>
        <div class="footer">THE END <br><br>扫码关注我们，获取最新清关及物流资讯。</div>
    </div>
</body>
</html>
"""

@st.cache_data(show_spinner=False)
def sniff_article_links(homepage_url):
    """智能嗅探首页/列表页上的最新文章链接 (加强版去噪)"""
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0'
    }
    try:
        response = requests.get(homepage_url, headers=headers, timeout=10)
        response.encoding = response.apparent_encoding
        soup = BeautifulSoup(response.text, 'html.parser')

        for tag in soup(['footer', 'header', 'nav', 'aside', 'script', 'style']):
            tag.decompose()
            
        links_data = []
        seen_urls = set()

        blacklist_keywords = [
            'icp', '备', '公网安', '许可证', '版权', 'copyright', 'all rights reserved', 
            '关于我们', '联系我们', '加入我们', '法律声明', '隐私政策', '服务条款',
            'about us', 'contact us', 'investor', 'privacy', 'terms', 'careers', 'sitemap'
        ]
        
        for a_tag in soup.find_all('a', href=True):
            url = a_tag['href'].strip()
            text = a_tag.get_text(strip=True)
            text_lower = text.lower()

            if len(text) < 12:
                continue

            if url.startswith(('#', 'javascript', 'mailto', 'tel')) or url.lower().endswith(('.pdf', '.jpg', '.png', '.zip', '.exe')):
                continue

            if any(kw in text_lower for kw in blacklist_keywords):
                continue

            full_url = urljoin(homepage_url, url)

            if full_url not in seen_urls:
                seen_urls.add(full_url)
                links_data.append({"title": text, "url": full_url})

        return links_data[:15]
    except Exception as e:
        return []
        

def scrape_website(url):
    """抓取网页正文（升级版：精准提取文章主体）"""

    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)'
    }

    try:
        response = requests.get(url, headers=headers, timeout=15)
        response.encoding = response.apparent_encoding
        soup = BeautifulSoup(response.text, 'html.parser')

        article_container = None

        possible_selectors = [
            'article',
            'main',
            '[role="main"]',
            '.article',
            '.article-content',
            '.post-content',
            '.entry-content',
            '.content',
            '.main-content',
            '#content'
        ]

        for selector in possible_selectors:
            article_container = soup.select_one(selector)
            if article_container:
                break

        if not article_container:
            article_container = soup

        for tag in article_container(['nav','footer','aside','script','style']):
            tag.decompose()

        paragraphs = article_container.find_all(['p','h1','h2','h3','li'])

        text_list = []

        blacklist = [
            'copyright',
            'all rights reserved',
            'privacy policy',
            'terms of use',
            'contact us'
        ]

        for p in paragraphs:

            text = p.get_text().strip()

            if len(text) < 30:
                continue

            if any(x in text.lower() for x in blacklist):
                continue

            text_list.append(text)

        text_content = "\n".join(text_list)

        text_content = text_content[:9000]

        images = []

        og_image = soup.find('meta', property='og:image')
        if og_image and og_image.get('content'):
            images.append(og_image.get('content'))

        for img in article_container.find_all('img'):

            src = img.get('src') or img.get('data-src')

            if not src:
                continue

            if src.startswith('/'):
                base_url = "/".join(url.split('/')[:3])
                src = base_url + src

            bad_keywords = [
                'logo','icon','avatar','svg','gif','base64','1x1','button'
            ]

            if any(x in src.lower() for x in bad_keywords):
                continue

            images.append(src)

        images = list(dict.fromkeys(images))[:3]

        return {
            "text": text_content,
            "images": images
        }

    except Exception as e:
        return {"error": str(e)}



def call_llm_generator(scraped_data, writing_style):
    system_prompt = f"""
    你现在是【头部专业清关与跨境物流公司的运营总监兼首席合规官】。
    你深谙欧美海关查验（如CBP、HMRC等）、关税政策、反倾销及合规化运营，拥有10年以上实战经验。

    【核心任务】：
    你需要把一篇较短或中等长度的英文资讯，**扩写并深度解析**成一篇不少于 2500 字的微信公众号爆款长文。
    **严禁只做简单的翻译或摘要！严禁短篇幅！**

    【如何做到长篇幅且不废话（重要扩写技法）】：
    1. **事件显微镜**：不要一笔带过原文。要把原文中的背景、人物表态、涉及公司、数据等细节，揉碎了详细描述。
    2. **历史纵深挖掘**：将该事件与过去几年的物流大事件（如T86严查、某某法案落地）结合起来对比分析，补充行业背景知识。
    3. **利益链条拆解**：这段新闻对“铺货型小白”、“品牌独立站大卖”、“传统海运货代”、“小包双清货代”分别会产生什么截然不同的影响？请分角色详细推演，制造痛点共鸣。
    4. **落地实操SOP**：不要只喊“要合规”的口号，必须给出具体的实操步骤（例如：审查报关单据的哪几项、如何选择尾程派送渠道、如何规避低申报红线等）。

    【合规与严谨底线】：
    客观数据、法案名称必须100%忠于原文，绝不编造；趋势预测需用“业内预判”、“可能引发”等严谨词汇；拒绝“包过”、“100%安全”等违规承诺。

    【行文风格】：
    必须以【{writing_style}】的角度来撰写。语气要像经历过行业大风大浪的老炮，语重心长且极为专业。
    """

    user_prompt = f"""
    【输入资料】：
    客观新闻/原文资料：{scraped_data['text']}
    可用配图URL列表：{json.dumps(scraped_data['images'], ensure_ascii=False)}

    【输出要求】：
    请严格返回合法的 JSON 格式，包含 `wechat` 和 `xhs_text` 两个字段。
    为了保证文章足够长且排版优美，**微信正文的每一个自然段，都必须是一个独立的 {{"type": "text"}} 对象！禁止把一大段几百字塞进一个 text 里！**

    请严格按照以下【五大部分】的结构生成 blocks（总 blocks 数量不应低于 20 个）：

    {{
        "wechat": {{
            "title": "直击痛点、包含核心关键词的微信标题（30字内）",
            "blocks": [
                // 【第一部分：事件深度复盘】（要求：详细展开原文，至少拆成3-4个独立的text块）
                {{ "type": "subtitle", "content": "一、风暴骤起：事件核心细节还原" }},
                {{ "type": "text", "content": "（第1段：引入新闻背景及核心人物/机构的动作...详细扩写，不少于150字）" }},
                {{ "type": "text", "content": "（第2段：原文中提到的具体公司、数据、或直接导火索...详细扩写，不少于150字）" }},
                {{ "type": "text", "content": "（第3段：外界或当事方的回应与态度...详细扩写）" }},
                {{ "type": "image", "url": "（从输入资料中挑1张）", "caption": "客观准确的配图说明" }},

                // 【第二部分：行业底层逻辑剖析】（要求：调用你的专家知识库补充背景）
                {{ "type": "subtitle", "content": "二、深度洞察：为何此时向物流企业发难？" }},
                {{ "type": "text", "content": "（第1段：结合当前宏观贸易环境、合规化大趋势进行分析...）" }},
                {{ "type": "text", "content": "（第2段：剖析涉事物流模式（如低价竞争、小包补贴等）对当地市场的冲击...）" }},
                {{ "type": "quote", "content": "（提炼一句极具洞察力的行业金句，如：‘廉价流量的红利期已过，合规才是跨境物流最后的护城河。’）" }},

                // 【第三部分：受众精准切片与影响推演】（要求：制造痛点共鸣，按角色分类讨论）
                {{ "type": "subtitle", "content": "三、连锁反应：谁将承受最痛的代价？" }},
                {{ "type": "text", "content": "（第1段：对【依赖低价小包的铺货卖家】的致命打击：时效延误、运费暴涨...）" }},
                {{ "type": "text", "content": "（第2段：对【中长尾跨境物流服务商】的洗牌效应：清关资质审核加剧...）" }},
                {{ "type": "text", "content": "（第3段：对【品牌出海企业】的启示：供应链安全的优先级将大于单纯的成本...）" }},

                // 【第四部分：破局与自查SOP】（要求：给出至少3条具体的行动指南）
                {{ "type": "subtitle", "content": "四、避坑指南：卖家与货代的紧急应对SOP" }},
                {{ "type": "text", "content": "（第1条建议：如：物流渠道溯源与风控排查...必须有具体的执行动作）" }},
                {{ "type": "text", "content": "（第2条建议：如：清关合规化升级，警惕‘双清包税’陷阱...）" }},
                {{ "type": "text", "content": "（第3条建议：如：数据隐私与在地化合规体系建设...）" }},
                {{ "type": "image", "url": "（如果有第2张图，请放在这里，没有就不用生成这行）", "caption": "规范化运营是长久之计" }},

                // 【第五部分：高管结语】
                {{ "type": "subtitle", "content": "五、写在最后" }},
                {{ "type": "text", "content": "（用大格局、有温度的话语总结全文，展望未来发展方向...）" }}
            ]
        }},
        "xhs_text": "【小红书纯文本】：\\n1. 标题：带情绪Emoji的行业预警或避坑提醒。\\n2. 正文结构：【发生什么（客观）】+【谁受影响（精准定位）】+【立刻自查3要点（合规建议）】。\\n3. 语气：专业但通俗，多用空行和 🔴✅ 符号。\\n4. 结尾：带 #跨境物流 #清关合规 等精准Tag。"
    }}

    注意：
    1. wechat.blocks 必须严格按上述【五大部分】的逻辑生成，你可以生成比示例更多的 block，但绝不能少！
    2. 每个 text block 不要超过 300 字，如果段落长，请拆分成多个连续的 text block。
    3. 微信正文的重点合规警示请用 **加粗** 标记。
    4. 只返回 JSON，不要输出任何额外的文本。
    """

    try:
        response = dashscope.Generation.call(
            model='qwen-max', 
            prompt=user_prompt,
            system_prompt=system_prompt,
            result_format='message',
            max_tokens=3000,
            temperature=0.7 # 稍微调低一点温度，防止模型在生成长JSON时逻辑跑偏或格式崩坏
        )
        if response.status_code == HTTPStatus.OK:
            content = response.output.choices[0].message.content
            # 清理可能的 markdown 格式
            content = re.sub(r'^```json\s*', '', content)
            content = re.sub(r'^```\s*', '', content)
            content = re.sub(r'\s*```$', '', content)
            
            try:
                return json.loads(content)
            except json.JSONDecodeError as e:
                # 容错处理：打印截断部分帮助调试
                print("JSON 解析失败，返回内容：", content[:500], "...")
                return {"error": f"LLM返回的格式不完整，可能超出了最大字数限制。请尝试重新生成。({str(e)})"}
        else:
            return {"error": response.message}
    except Exception as e:
        return {"error": str(e)}


def process_text_format(text):
    if not text: return ""
    text = re.sub(r'\*\*(.*?)\*\*', r'<span class="highlight">\1</span>', text)
    return text


def render_wechat_html(ai_data, style_name):
    wechat_data = ai_data.get("wechat", {})
    for block in wechat_data.get("blocks", []):
        if block["type"] in ["text", "subtitle", "quote"]:
            block["content"] = process_text_format(block.get("content", ""))

    template = Template(WECHAT_HTML_TEMPLATE)
    return template.render(
        article=wechat_data,
        date=datetime.datetime.now().strftime("%Y-%m-%d"),
        style_name=style_name
    )


def main():
    with st.sidebar:
        st.image("https://img.alicdn.com/tfs/TB1pjlkwYj1gK0jSZFOXXc7GpXa-1000-1000.png", width=60)
        st.title("使用说明")
        st.markdown("---")
        st.markdown("""
        **生成流程**：
        1. 在主界面粘贴想要抓取的物流新闻链接，按下Enter键。
        2. 选择想要抓取的文章。
        2. 勾选你想生成的不同观看受众视角。
        3. 点击生成，进入双屏排版预览台。
        4. 一键拷贝。
        """)

    st.title("🚀 跨境物流日常公众号&小红书推文AI自动抓取生成工作台")
    st.markdown("输入外媒原始资讯，一键转化为 **精美微信公众号** + **高赞小红书种草文**。")
    st.markdown("---")

    target_url = st.text_input("🔗 粘贴目标网页链接 (可以是详情页，也可以是新闻列表页):", placeholder="https://www...")

    final_article_url = target_url

    if target_url:
        with st.spinner("🔍 正在嗅探网页链接..."):
            possible_links = sniff_article_links(target_url)
            
        if possible_links:
            st.success(f"雷达扫描到该网页下有 {len(possible_links)} 篇最新资讯！")

            options = ["👉 [这是具体的文章页面，直接抓取当前链接]"] + [f"📄 {item['title']}" for item in possible_links]
            selected_option = st.selectbox("请确认您要抓取哪一篇文章：", options)
            
            if selected_option != options[0]:
                selected_index = options.index(selected_option) - 1
                final_article_url = possible_links[selected_index]['url']
                st.info(f"即将抓取: {final_article_url}")

    st.markdown("---")
    selected_styles = st.multiselect(
        "🎯 选择想要生成的文案风格 (勾选几个就生成几篇):",
        WRITING_STYLES,
        default=[WRITING_STYLES[0], WRITING_STYLES[1]]
    )

    if st.button("🚀 立即生成文章", use_container_width=True, type="primary"):
        if not final_article_url:
            st.warning("⚠️ 请输入目标网页链接！")
            st.stop()
        if not selected_styles:
            st.warning("⚠️ 请至少选择一种生成风格！")
            st.stop()

        if 'generated_results' in st.session_state:
            del st.session_state['generated_results']
        st.session_state['generated_results'] = []

        with st.status(f"🕸️ 正在提取文章核心内容...", expanded=True) as status:
            scraped_data = scrape_website(final_article_url) 
            if "error" in scraped_data:
                status.update(label=f"抓取失败: {scraped_data['error']}", state="error")
                st.stop()
            else:
                st.write(f"✅ 提取成功：{len(scraped_data['text'])} 字正文，{len(scraped_data['images'])} 张可用配图")
                status.update(label="网页抓取成功！", state="complete", expanded=False)
                
        progress_bar = st.progress(0)
        for i, style in enumerate(selected_styles):
            with st.spinner(f"🧠 正在以【{style.split(' ')[0]}】视角撰稿与排版..."):
                ai_data = call_llm_generator(scraped_data, style)

                if "error" in ai_data:
                    st.error(f"生成失败: {ai_data['error']}")
                    continue

                html_content = render_wechat_html(ai_data, style)
                xhs_content = ai_data.get("xhs_text", "小红书生成失败")

                st.session_state['generated_results'].append({
                    "style_short": style.split(" ")[0],
                    "html": html_content,
                    "xhs": xhs_content,
                    "title": ai_data.get("wechat", {}).get("title", "未命名标题")
                })

            progress_bar.progress((i + 1) / len(selected_styles))

        st.success("🎉 所有矩阵文案生成完毕！请在下方进行审校和拷贝。")


    if st.session_state.get('generated_results'):
        st.markdown("## 📊 多版本审阅工作台")

        tab_names = [res["style_short"] for res in st.session_state['generated_results']]
        tabs = st.tabs(tab_names)

        for i, tab in enumerate(tabs):
            res = st.session_state['generated_results'][i]
            with tab:
                col1, col2 = st.columns([1.2, 1], gap="large")

                with col1:
                    st.subheader("🟢 微信公众号实时预览")
                    st.info("💡 提示：在网页中 `Ctrl+A` 全选，直接拷贝到微信公众号后台即可完美保留格式！")

                    components.html(res["html"], height=700, scrolling=True)

                    st.download_button(
                        label="⬇️ 导出为 HTML 文件",
                        data=res["html"],
                        file_name=f"公众号_{res['title']}.html",
                        mime="text/html",
                        key=f"dl_wechat_{i}"
                    )

                with col2:
                    st.subheader("🔴 小红书直接发布版")
                    st.info("💡 提示：点击代码框右上角的“复制”图标，一键提取到手机发布！")

                    st.code(res["xhs"], language="markdown")

                    st.download_button(
                        label="⬇️ 导出为 TXT 文件",
                        data=res["xhs"],
                        file_name=f"小红书_{res['title']}.txt",
                        mime="text/plain",
                        key=f"dl_xhs_{i}"
                    )


if __name__ == "__main__":
    main()





