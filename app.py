import os
import json
import urllib.parse
import streamlit as st
from openai import OpenAI
from streamlit_agraph import agraph, Node, Edge, Config

# 1. 环境防护：彻底切断代理干扰，确保 API 请求稳定
os.environ["http_proxy"] = ""
os.environ["https_proxy"] = ""
os.environ["HTTP_PROXY"] = ""
os.environ["HTTPS_PROXY"] = ""

st.set_page_config(page_title="AI 智教：北科大 CS 保研全能版", page_icon="🎓", layout="wide")

# 2. 初始化核心状态 (Session State)
if 'exp' not in st.session_state:
    st.session_state.exp = 0
if 'completed_nodes' not in st.session_state:
    st.session_state.completed_nodes = []
if 'dynamic_tree' not in st.session_state:
    st.session_state.dynamic_tree = None
if 'target_node' not in st.session_state:
    st.session_state.target_node = None
if 'question' not in st.session_state:
    st.session_state.question = ""
if 'comp_radar' not in st.session_state:
    st.session_state.comp_radar = ""

# 3. 侧边栏：学习者画像与中控台
with st.sidebar:
    st.title("⚙️ 智教控制台")
    api_key = st.text_input("🔑 智谱 API Key", type="password", help="在此输入你的智谱 API Key 并回车")
    st.markdown("---")
    
    st.header("👤 学习者画像")
    user_stage = st.selectbox(
        "当前年级", 
        ["大一新生 (探索期)", "大二学生 (发力期)", "大三学生 (冲刺期)", "大四学生 (决战期)"]
    )
    user_goal = st.text_input("核心学习目标", value="学习 C++，备战蓝桥杯，冲击保研")
    
    st.markdown("---")
    lv = st.session_state.exp // 100 + 1
    st.metric("🏆 学习者等级", f"Lv.{lv}")
    st.write(f"经验值: {st.session_state.exp % 100} / 100")
    st.progress(min((st.session_state.exp % 100) / 100, 1.0))

client = None
if api_key:
    client = OpenAI(api_key=api_key, base_url="https://open.bigmodel.cn/api/paas/v4")

st.title("🎓 AI 智教：基于北科大方案的全周期路径系统")

tab1, tab2, tab3 = st.tabs(["🗺️ AI 演算科技树", "⚔️ 力扣(LeetCode)实战大厅", "🏆 保研竞赛雷达(加分专属)"])

# ==================== 功能区 1：AI 动态演算科技树 (核心大脑) ====================
with tab1:
    if st.button("🚀 启动 AI 路径演算", type="primary"):
        if not client:
            st.error("请先在左侧输入 API Key！")
        else:
            with st.spinner("AI 导师正在演算路径，请稍候..."):
                sys_prompt = f"""你是一个极其严苛的计算机教务架构师。
                用户身份：{user_stage}，核心目标：{user_goal}。
                
                【致命约束条件 - 拒绝冗余】：
                1. 严禁生成内容重复或高度相似的节点：绝对不要同时出现“程序设计基础”和“C++入门”，必须将校内课程与用户的学习目标深度融合，合并为一个节点。
                2. 严禁单线串联：必须生成带有多个分叉的“树状拓扑图”。
                3. 严密的先修逻辑：source 必须是 target 的基础课。
                4. 输出纯 JSON 格式，包含 'nodes' 和 'edges'。
                5. 每个 node 必须包含 'stage' 字段，值为 '大一', '大二', '大三', '拓展' 之一。
                
                参考格式：
                {{
                    "nodes": [
                        {{"id": "n1", "label": "程序设计基础A(C++)", "source": "校内", "stage": "大一"}},
                        {{"id": "n2", "label": "数据结构A", "source": "校内", "stage": "大二"}},
                        {{"id": "n3", "label": "蓝桥杯/CCPC专题", "source": "拓展", "stage": "拓展"}}
                    ],
                    "edges": [
                        {{"source": "n1", "target": "n2"}},
                        {{"source": "n2", "target": "n3"}}
                    ]
                }}"""
                try:
                    res = client.chat.completions.create(
                        model="glm-4-flash", 
                        messages=[{"role": "user", "content": sys_prompt}],
                        temperature=0.2, 
                        max_tokens=2048
                    )
                    raw_text = res.choices[0].message.content.strip().replace('```json', '').replace('```', '')
                    temp_tree = json.loads(raw_text)
                    
                    if 'nodes' in temp_tree and 'edges' in temp_tree:
                        st.session_state.dynamic_tree = temp_tree
                        
                        # 智能免修逻辑
                        user_lvl = 1
                        if "大二" in user_stage: user_lvl = 2
                        elif "大三" in user_stage: user_lvl = 3
                        elif "大四" in user_stage: user_lvl = 4
                        
                        st.session_state.completed_nodes = [
                            n['id'] for n in temp_tree['nodes'] 
                            if (user_lvl >= 2 and n.get('stage') == "大一") or \
                               (user_lvl >= 3 and n.get('stage') == "大二") or \
                               (user_lvl >= 4 and n.get('stage') == "大三")
                        ]
                        st.session_state.target_node = None
                        st.success("✅ 演算成功！已合并重复节点并优化布局。")
                    else:
                        st.error("AI 生成的结构不完整，请重试。")
                except Exception as e:
                    st.error(f"⚠️ 解析失败: {e}")

    # 渲染图谱逻辑
    if st.session_state.dynamic_tree:
        tree = st.session_state.dynamic_tree
        
        dynamic_prereqs = {}
        for edge in tree.get('edges', []):
            dynamic_prereqs.setdefault(edge['target'], []).append(edge['source'])
        
        dynamic_base_nodes = [n['id'] for n in tree['nodes'] if n['id'] not in dynamic_prereqs]

        def is_dynamic_unlocked(nid):
            if nid in dynamic_base_nodes: return True
            prereqs = dynamic_prereqs.get(nid, [])
            return all(req in st.session_state.completed_nodes for req in prereqs)

        nodes = []
        for n in tree['nodes']:
            src = n.get('source', '校内')
            if n['id'] in st.session_state.completed_nodes:
                color = "#FFD700" 
            elif not is_dynamic_unlocked(n['id']):
                color = "#4F4F4F" 
            else:
                color = "#1E90FF" if src == "校内" else "#9370DB" 
            
            # 使用较宽的垂直边距防止重叠
            nodes.append(Node(id=n['id'], label=f"{n['label']}\n[{src}]", color=color, size=35))
        
        edges = [Edge(source=e['source'], target=e['target'], color="#AAAAAA") for e in tree.get('edges', [])]
        
        config = Config(
            width=1000, 
            height=600, 
            directed=True, 
            physics=False, 
            hierarchical=True, 
            layout={
                "hierarchical": {
                    "enabled": True, 
                    "direction": "UD", 
                    "sortMethod": "directed",
                    "nodeSpacing": 300,      # 再次增加节点水平间距
                    "levelSeparation": 180,  # 再次增加层级垂直间距
                    "edgeMinimization": True
                }
            }
        )
        
        clicked = agraph(nodes=nodes, edges=edges, config=config)

        if clicked:
            node_data = next((n for n in tree['nodes'] if n['id'] == clicked), None)
            if node_data:
                st.markdown("---")
                
                # ！！！ 核心修复：人工校验的离散数学及全套名师链接 ！！！
                verified_direct_links = {
                    "程序设计基础": "https://www.bilibili.com/video/BV1et411b73Z/",
                    "C++": "https://www.bilibili.com/video/BV1et411b73Z/",
                    "C语言": "https://www.bilibili.com/video/BV1q54y1q79w/",
                    "数据结构": "https://www.bilibili.com/video/BV1JW411i731/",
                    "算法": "https://www.bilibili.com/video/BV1A4411v7hK/",
                    "组成原理": "https://www.bilibili.com/video/BV1c4411w7nd/",
                    "操作系统": "https://www.bilibili.com/video/BV1YE411D7nH/",
                    "计算机网络": "https://www.bilibili.com/video/BV19E411D78Q/",
                    "编译原理": "https://www.bilibili.com/video/BV1zW411t7YE/",
                    # 纠错：离散数学使用北大屈婉玲教授经典版
                    "离散数学": "https://www.bilibili.com/video/BV1kx411D71x/", 
                    "数学分析": "https://www.bilibili.com/video/BV1Eb411u7Fw/",
                    "线性代数": "https://www.bilibili.com/video/BV1aW411Q7x1/",
                    "概率论": "https://www.bilibili.com/video/BV1ot411y7mU/",
                    "数据库": "https://www.bilibili.com/video/BV1tY4y1D7nZ/",
                    "人工智能": "https://www.bilibili.com/video/BV1Pa411X76s/",
                    "机器学习": "https://www.bilibili.com/video/BV1Pa411X76s/",
                    "深度学习": "https://www.bilibili.com/video/BV18K411w7cE/",
                    "前端": "https://www.bilibili.com/video/BV1Y84y1L7Nn/",
                    "React": "https://www.bilibili.com/video/BV1mE411n7oG/",
                    "Vue": "https://www.bilibili.com/video/BV1Zy4y1K7SH/",
                    "Java": "https://www.bilibili.com/video/BV1Kb411W75N/",
                    "Python": "https://www.bilibili.com/video/BV1qW4y1a7fU/",
                    "Linux": "https://www.bilibili.com/video/BV187411y7hF/",
                    "蓝桥杯": "https://search.bilibili.com/all?keyword=蓝桥杯真题精讲",
                    "CCPC": "https://search.bilibili.com/all?keyword=CCPC算法竞赛",
                    "LeetCode": "https://www.bilibili.com/video/BV1vK4y1o7jH/"
                }
                
                final_link = ""
                course_text = (node_data['label'] + node_data.get('course_name', '')).upper()
                for key, url in verified_direct_links.items():
                    if key.upper() in course_text:
                        final_link = url
                        break
                
                if not final_link:
                    safe_keyword = urllib.parse.quote(node_data.get('course_name', node_data['label']))
                    final_link = f"https://search.bilibili.com/all?keyword={safe_keyword}"
                
                st.info(f"📍 选中节点：{node_data['label']}")
                course_display = f"[{node_data.get('course_name', node_data['label'])} (点击直达▶️)]({final_link})"
                
                if clicked in st.session_state.completed_nodes:
                    st.success("🎉 该节点已免修或点亮掌握！")
                    st.markdown(f"**📚 温故知新：** {course_display}")
                    st.session_state.target_node = clicked
                elif not is_dynamic_unlocked(clicked):
                    st.error(f"🔒 节点未解锁！请先完成前置。")
                else:
                    st.session_state.target_node = clicked
                    st.markdown(f"👉 **锁定目标！推荐网课直通车：** {course_display}")

# ==================== 功能区 2：力扣(LeetCode)实战大厅 ====================
with tab2:
    if not st.session_state.target_node:
        st.warning("⚠️ 请先在科技树点击考核目标！")
    else:
        node_id = st.session_state.target_node
        st.subheader(f"⚔️ 【{node_id}】算法/逻辑实战考核")
        
        if st.button("🎲 从力扣/竞赛库抽取真题", use_container_width=True):
            with st.spinner("正在抽取真题..."):
                try:
                    q_prompt = f"针对【{node_id}】，我是{user_stage}，出一道 LeetCode 风格的算法题。包含题目、示例、范围。不要给答案。"
                    res = client.chat.completions.create(model="glm-4-flash", messages=[{"role": "user", "content": q_prompt}])
                    st.session_state.question = res.choices[0].message.content
                except Exception as e:
                    st.error(f"出题失败: {e}")
        
        if st.session_state.question:
            st.markdown(st.session_state.question)
            ans = st.text_area("⌨️ 编写你的代码实现或思路：", height=250)
            if st.button("🚀 提交评测 (Run Code)"):
                with st.spinner("判题机正在审阅..."):
                    try:
                        res = client.chat.completions.create(
                            model="glm-4-flash", 
                            messages=[{"role": "user", "content": f"题目：{st.session_state.question}\n我的回答：{ans}\n请判题，正确请在开头说'通过'。"}]
                        )
                        st.write("### 👨‍🏫 OJ 评测结果")
                        st.write(res.choices[0].message.content)
                        if "通过" in res.choices[0].message.content:
                            st.success("Accepted！经验 +100")
                            if node_id not in st.session_state.completed_nodes:
                                st.session_state.completed_nodes.append(node_id)
                                st.session_state.exp += 100
                            st.balloons()
                    except Exception as e:
                        st.error(f"测评失败: {e}")

# ==================== 功能区 3：保研竞赛雷达 (加分专题) ====================
with tab3:
    st.subheader("🏆 保研加分赛事扫描雷达")
    
    if st.button("🔍 一键扫描适配保研赛事", type="primary", use_container_width=True):
        if not client:
            st.error("请先在左侧输入 API Key！")
        else:
            with st.spinner("检索中..."):
                try:
                    radar_prompt = f"根据年级{user_stage}和目标{user_goal}，推荐 5-6 个保研加分白名单赛事。详细说明含金量、建议。"
                    res = client.chat.completions.create(model="glm-4-flash", messages=[{"role": "user", "content": radar_prompt}])
                    st.session_state.comp_radar = res.choices[0].message.content
                except Exception:
                    st.session_state.comp_radar = """
                    ### 🏆 本地核心赛事数据库 (教育部白名单)
                    1. **蓝桥杯全国软件人才大赛 (国A类)**：省一及以上加分显著。
                    2. **ACM-ICPC / CCPC 国际程序设计竞赛**：保研免面试金牌。
                    3. **中国大学生计算机设计大赛**：作品类竞赛，含金量稳定。
                    4. **“挑战杯”科技作品竞赛 (国A类)**：综合实力体现。
                    5. **“互联网+”大学生创新创业大赛 (国A类)**：目前分值最大的赛事。
                    """
    
    if st.session_state.comp_radar:
        st.markdown(st.session_state.comp_radar)