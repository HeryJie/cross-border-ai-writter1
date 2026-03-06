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
# ============================================================
#  页面全局配置 (必须放在最前面)
# ============================================================
st.set_page_config(
    page_title="跨境物流 AI 爆款生成器",
    page_icon="🚀",
    layout="wide"
)

# ============================================================
#  配置与常量
# ============================================================
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


# ============================================================
#  核心逻辑层
# ============================================================
@st.cache_data(show_spinner=False)
def sniff_article_links(homepage_url):
    """智能嗅探首页/列表页上的最新文章链接"""
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0'
    }
    try:
        response = requests.get(homepage_url, headers=headers, timeout=10)
        soup = BeautifulSoup(response.text, 'html.parser')
        
        links_data = []
        seen_urls = set()
        
        # 寻找网页中的所有超链接
        for a_tag in soup.find_all('a', href=True):
            url = a_tag['href']
            text = a_tag.get_text(strip=True)
            
            # 过滤规则：
            # 1. 标题太短的不要（通常是导航按钮如 "Home", "Contact"）
            # 2. 链接不能是锚点 # 或 javascript
            if len(text) > 15 and not url.startswith(('#', 'javascript', 'mailto')):
                # 补全相对链接为绝对链接
                full_url = urljoin(homepage_url, url)
                
                # 简单去重
                if full_url not in seen_urls:
                    seen_urls.add(full_url)
                    links_data.append({"title": text, "url": full_url})
        
        # 返回前 15 条最像文章的链接
        return links_data[:15]
    except Exception as e:
        return []
        
def scrape_website(url):
    """抓取网页，使用 cache 避免重复抓取"""
    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }
    try:
        response = requests.get(url, headers=headers, timeout=15)
        response.encoding = response.apparent_encoding
        soup = BeautifulSoup(response.text, 'html.parser')

        paragraphs = soup.find_all(['p', 'h1', 'h2', 'h3', 'li'])
        text_content = "\n".join([p.get_text().strip() for p in paragraphs if len(p.get_text().strip()) > 10])
        text_content = text_content[:6000]

        images = []
        og_image = soup.find('meta', property='og:image')
        if og_image and og_image.get('content'):
            images.append(og_image.get('content'))

        for img in soup.find_all('img'):
            src = img.get('src') or img.get('data-src')
            if src:
                if src.startswith('/'):
                    base_url = "/".join(url.split('/')[:3])
                    src = base_url + src
                bad_keywords = ['logo', 'icon', 'svg', 'avatar', 'banner', 'button', 'base64', 'gif', '1x1']
                if not any(x in src.lower() for x in bad_keywords):
                    images.append(src)

        images = list(dict.fromkeys(images))[:3]
        return {"text": text_content, "images": images}
    except Exception as e:
        return {"error": str(e)}


def call_llm_generator(scraped_data, writing_style):
    system_prompt = f"""
    你是一位顶级的跨境物流资深主编兼新媒体排版大师。
    请基于抓取的内容和提供的图片，生成两份**完全独立**的内容格式。

    【核心要求】：
    1. **本次行文侧重点**：必须以【{writing_style}】的角度来撰写。
    2. **打破固定长度**：根据原文的信息量，自由展开深度。生成深度的长文（可达 1000-1500 字），划分 5-6 个小标题详尽解析。
    3. **动态数组**：wechat.blocks 数组长度自由决定。
    """

    user_prompt = f"""
    【原文资料】：{scraped_data['text']}
    【可用图片URL列表】：{json.dumps(scraped_data['images'], ensure_ascii=False)}

    请务必只返回合法的 JSON 格式：
    {{
        "wechat": {{
            "title": "符合设定风格的微信爆款标题",
            "blocks": [
                {{ "type": "text", "content": "内容..." }},
                {{ "type": "image", "url": "挑选列表中的图片", "caption": "图片说明" }},
                {{ "type": "subtitle", "content": "小标题..." }}
            ]
        }},
        "xhs_text": "此处直接输出为你排版好的小红书纯文本！包含标题、正文结构、Emoji和热门标签。"
    }}
    注意：wechat.blocks type 只能是 text, subtitle, quote, image。微信重点词语用 **加粗**。
    """

    try:
        response = dashscope.Generation.call(
            model='qwen-plus',
            prompt=user_prompt,
            system_prompt=system_prompt,
            result_format='message'
        )
        if response.status_code == HTTPStatus.OK:
            content = response.output.choices[0].message.content
            content = re.sub(r'^```json\s*', '', content)
            content = re.sub(r'^```\s*', '', content)
            content = re.sub(r'\s*```$', '', content)
            return json.loads(content)
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


# ============================================================
#  Streamlit UI 构建
# ============================================================
def main():
    # 侧边栏配置
    with st.sidebar:
        st.image("https://img.alicdn.com/tfs/TB1pjlkwYj1gK0jSZFOXXc7GpXa-1000-1000.png", width=60)
        st.title("使用说明")
        st.markdown("---")
        # api_key = st.text_input("🔑 阿里云 API Key", value=DEFAULT_API_KEY, type="password")
        # dashscope.api_key = api_key

        st.markdown("""
        **生成流程**：
        1. 在主界面粘贴想要抓取的物流新闻链接。
        2. 勾选你想生成的不同观看受众视角。
        3. 点击生成，进入双屏排版预览台。
        4. 一键拷贝。
        """)

    st.title("🚀 跨境物流日常公众号&小红书推文AI自动抓取生成工作台")
    st.markdown("输入外媒原始资讯，一键转化为 **精美微信公众号** + **高赞小红书种草文**。")
    st.markdown("---")

    # ================= 智能 URL 交互区 =================
    target_url = st.text_input("🔗 粘贴目标网页链接 (可以是详情页，也可以是新闻列表页):", placeholder="https://www...")
    
    # 真正的抓取目标地址（可能等于用户输入的，也可能是用户从下拉框选的）
    final_article_url = target_url

    if target_url:
        # 如果用户输入了链接，先探测一下这个网页里有没有其他文章链接
        with st.spinner("🔍 正在嗅探网页链接..."):
            possible_links = sniff_article_links(target_url)
            
        if possible_links:
            # 如果嗅探到了链接，说明用户可能输入了一个主页/列表页
            st.success(f"雷达扫描到该网页下有 {len(possible_links)} 篇最新资讯！")
            
            # 把提取到的标题做成下拉菜单供客户选择
            options = ["👉 [这是具体的文章页面，直接抓取当前链接]"] + [f"📄 {item['title']}" for item in possible_links]
            selected_option = st.selectbox("请确认您要抓取哪一篇文章：", options)
            
            if selected_option != options[0]:
                # 如果客户选了下拉框里的某篇，就把抓取目标换成对应的 URL
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
            
        # ---------- 后续逻辑完全不变，只是把 target_url 换成 final_article_url ----------
        if 'generated_results' in st.session_state:
            del st.session_state['generated_results']
        st.session_state['generated_results'] = []

        # 1. 抓取网页阶段
        with st.status(f"🕸️ 正在提取文章核心内容...", expanded=True) as status:
            scraped_data = scrape_website(final_article_url)  # <--- 这里换成 final_article_url
            if "error" in scraped_data:
                status.update(label=f"抓取失败: {scraped_data['error']}", state="error")
                st.stop()
            else:
                st.write(f"✅ 提取成功：{len(scraped_data['text'])} 字正文，{len(scraped_data['images'])} 张可用配图")
                status.update(label="网页抓取成功！", state="complete", expanded=False)
                
        # 2. AI 生成阶段
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

            # 更新进度条
            progress_bar.progress((i + 1) / len(selected_styles))

        st.success("🎉 所有矩阵文案生成完毕！请在下方进行审校和拷贝。")

    # ============================================================
    #  结果展示工作台 (只在生成后显示)
    # ============================================================
    if st.session_state.get('generated_results'):
        st.markdown("## 📊 多版本审阅工作台")

        # 动态生成标签页
        tab_names = [res["style_short"] for res in st.session_state['generated_results']]
        tabs = st.tabs(tab_names)

        for i, tab in enumerate(tabs):
            res = st.session_state['generated_results'][i]
            with tab:
                # 左右双栏布局
                col1, col2 = st.columns([1.2, 1], gap="large")

                # 左侧：微信公众号
                with col1:
                    st.subheader("🟢 微信公众号实时预览")
                    st.info("💡 提示：在网页中 `Ctrl+A` 全选，直接拷贝到微信公众号后台即可完美保留格式！")

                    # 使用内嵌 HTML 组件渲染排版效果，高度设为 800px 支持内滚
                    components.html(res["html"], height=700, scrolling=True)

                    # 提供下载按钮
                    st.download_button(
                        label="⬇️ 导出为 HTML 文件",
                        data=res["html"],
                        file_name=f"公众号_{res['title']}.html",
                        mime="text/html",
                        key=f"dl_wechat_{i}"
                    )

                # 右侧：小红书文案
                with col2:
                    st.subheader("🔴 小红书直接发布版")
                    st.info("💡 提示：点击代码框右上角的“复制”图标，一键提取到手机发布！")

                    # 使用代码块展示，自带一键拷贝按钮
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



