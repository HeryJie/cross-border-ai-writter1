import streamlit as st
import requests
import json
import datetime
import re
from bs4 import BeautifulSoup
import trafilatura
from jinja2 import Template
import dashscope
from dashscope.api_entities.dashscope_response import HTTPStatus

# ===============================
# 页面配置
# ===============================

st.set_page_config(
    page_title="AI物流新闻生成器",
    page_icon="🚀",
    layout="wide"
)

# ===============================
# API KEY
# ===============================

try:
    dashscope.api_key = st.secrets["DASHSCOPE_API_KEY"]
except:
    dashscope.api_key = ""

# ===============================
# 写作风格
# ===============================

WRITING_STYLES = [
    "专业深度政策解读",
    "跨境卖家风险提醒",
    "宏观趋势分析",
    "突发新闻速读",
    "轻松吐槽风格"
]

# ===============================
# 微信HTML模板
# ===============================

WECHAT_TEMPLATE = """
<html>
<head>
<meta charset="utf-8">
<style>
body{font-family:Arial;padding:20px;background:#f5f5f5}
.container{background:white;padding:30px;border-radius:10px}
h1{font-size:26px}
p{font-size:16px;line-height:1.8}
.subtitle{font-size:20px;font-weight:bold;margin-top:30px}
img{max-width:100%;margin:20px 0;border-radius:6px}
</style>
</head>

<body>
<div class="container">

<h1>{{title}}</h1>

<p style="color:gray">{{date}}</p>

{% for block in blocks %}

{% if block.type=="text" %}
<p>{{block.content}}</p>
{% endif %}

{% if block.type=="subtitle" %}
<div class="subtitle">{{block.content}}</div>
{% endif %}

{% if block.type=="image" %}
<img src="{{block.url}}">
{% endif %}

{% endfor %}

</div>
</body>
</html>
"""

# ===============================
# 智能正文提取
# ===============================

def extract_article(url):

    headers = {
        "User-Agent":"Mozilla/5.0"
    }

    html = requests.get(url,headers=headers).text

    # 第一层：trafilatura智能提取
    text = trafilatura.extract(html)

    soup = BeautifulSoup(html,"html.parser")

    images=[]

    for img in soup.find_all("img"):

        src = img.get("src")

        if not src:
            continue

        if "logo" in src.lower():
            continue

        if src.startswith("/"):
            base=url.split("/")[0]+"//"+url.split("/")[2]
            src=base+src

        images.append(src)

    images=list(dict.fromkeys(images))[:3]

    return {
        "text":text[:6000],
        "images":images
    }

# ===============================
# AI生成
# ===============================

def generate_ai(scraped,style):

    system_prompt=f"""
你是一名资深跨境物流媒体编辑。

根据原始新闻写一篇公众号文章。

要求：

1 深度分析
2 800-1200字
3 5个小标题
4 风格：{style}

返回JSON：
"""

    user_prompt=f"""

原文：

{scraped['text']}

图片：

{scraped['images']}

返回：

{{
"title":"标题",
"blocks":[
{{"type":"text","content":"..."}},
{{"type":"subtitle","content":"..."}},
{{"type":"image","url":"..."}}
],
"xhs":"小红书文案"
}}

"""

    response=dashscope.Generation.call(
        model="qwen-plus",
        prompt=user_prompt,
        system_prompt=system_prompt,
        result_format="message"
    )

    if response.status_code==HTTPStatus.OK:

        txt=response.output.choices[0].message.content

        txt=re.sub("```json","",txt)
        txt=re.sub("```","",txt)

        return json.loads(txt)

    else:
        return {"error":"AI生成失败"}

# ===============================
# 渲染HTML
# ===============================

def render_html(article):

    template=Template(WECHAT_TEMPLATE)

    return template.render(
        title=article["title"],
        date=datetime.date.today(),
        blocks=article["blocks"]
    )

# ===============================
# UI
# ===============================

st.title("🚀 AI跨境物流新闻生成器")

url=st.text_input("输入新闻链接")

style=st.selectbox("选择写作风格",WRITING_STYLES)

if st.button("开始生成"):

    if not url:
        st.warning("请输入链接")
        st.stop()

    with st.spinner("抓取网页内容..."):

        data=extract_article(url)

    st.success(f"抓取完成：{len(data['text'])} 字")

    with st.spinner("AI生成文章..."):

        result=generate_ai(data,style)

    if "error" in result:
        st.error("生成失败")
        st.stop()

    html=render_html(result)

    col1,col2=st.columns(2)

    with col1:

        st.subheader("公众号预览")

        st.components.v1.html(html,height=700)

        st.download_button(
            "下载HTML",
            html,
            file_name="wechat.html"
        )

    with col2:

        st.subheader("小红书文案")

        st.code(result["xhs"])

        st.download_button(
            "下载TXT",
            result["xhs"],
            file_name="xhs.txt"
        )
