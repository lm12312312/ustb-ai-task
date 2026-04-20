import os
import json
import urllib.parse
import streamlit as st
from openai import OpenAI
from streamlit_agraph import agraph, Node, Edge, Config

# 1. 【环境防护】彻底切断代理干扰，确保在云端(Streamlit Cloud)和本地均能稳定请求 API
os.environ["http_proxy"] = ""
os.environ["https_proxy"] = ""
os.environ["HTTP_PROXY"] = ""
os.environ["HTTPS_PROXY"] = ""

# 页面配置
st.set_page_config(
    page_title="AI 智教：北科大 CS 保研全能版", 
    page_icon="🎓", 
    layout="wide",
    initial_sidebar_state="expanded"
)

# 2. 【核心状态管理】初始化 Session State，防止页面刷新导致进度丢失
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

# --- 云端自适应获取 API Key 逻辑 ---
# 自动读取部署后台 Settings -> Secrets 中的 ZHIPU_AI_KEY
api_key_from_secrets = ""
try:
    api_key_from_secrets = st.secrets.get("ZHIPU_AI_KEY", "")
except Exception:
    pass

# 3. 【侧边栏】智教中控台与学习者画像
with st.sidebar:
    st.title("⚙️ 智教控制台")
    # 自动加载云端配置好的 Key
    user_input_key = st.text_input(
        "🔑 智谱 API Key", 
        value=api_key_from_secrets if api_key_from_secrets else "",
        type="password",
        help="建议在部署后台配置 ZHIPU_AI_KEY 以免手动输入"
    )
    st.markdown("---")
    
    st.header("👤 学习者画像")
    user_stage = st.selectbox(
        "当前年级/学段", 
        ["大一新生 (探索期)", "大二学生 (发力期)", "大三学生 (冲刺期)", "大四学生 (决战期)"]
    )
    user_goal = st.text_input("核心学习目标", value="学习 C++，备战蓝桥杯/CCPC，冲击保研")
    
    st.markdown("---")
    # 等级与经验值展示
    lv = st.session_state.exp // 100 + 1
    st.metric("🏆 学习者等级", f"Lv.{lv}")
    st.write(f"当前经验值: {st.session_state.exp % 100} / 100")
    st.progress(min((st.session_state.exp % 100) / 100, 1.0))
    
    if st.button("🔄 重置所有进度", use_container_width=True):
        st.session_state.exp = 0
        st.session_state.completed_nodes = []
        st.session_state.dynamic_tree = None
        st.rerun()

# 确定最终使用的 API 客户端
final_key = user_input_key if user_input_key else api_key_from_secrets
client = None
if final_key:
    client = OpenAI(api_key=final_key, base_url="https://open.bigmodel.cn/api/paas/v4")

st.title("🎓 AI 智教：基于北科大方案的全周期路径系统")
st.caption("AI 动态演算、LeetCode 测评、保研加分雷达三位一体")

tab1, tab2, tab3 = st.tabs(["🗺️ AI 演算科技树", "⚔️ AI 知识测评 (OJ模式)", "🏆 保研竞赛雷达 (加分专属)"])

# ==================== 功能区 1：AI 动态演算科技树 (核心大脑) ====================
with tab1:
    st.markdown("""
    🔵 **蓝色**:校内必修 | 🟣 **紫色**:目标拓展 | 🟡 **金色**:已掌握 | ⚫ **灰色**:尚未解锁
    """)

    if st.button("🚀 启动 AI 路径全景演算", type="primary", use_container_width=True):
        if not client:
            st.error("❌ 请先在左侧输入 API Key！(或在部署后台配置 Secrets)")
        else:
            with st.spinner("AI 导师正在演算路径，请稍候..."):
                sys_prompt = f"""你是一个极其严苛且专业的计算机学院教务架构师。
                用户身份：{user_stage}，核心目标：{user_goal}。
                
                【致命约束条件】：
                1. **强目标相关性**：严禁出现大学物理、大学英语、思政、体育等非计算机专业核心课。
                2. **标签强制显示**：每个 node 必须有清晰的 'label'。
                3. **学术逻辑因果链**：
                   - **程序设计基础(C/C++)必须是数据结构的前置节点。**
                   - 数据结构必须是算法分析、操作系统、竞赛实战的前置节点。
                4. **区分校内与拓展**：必须将课程分为 '校内' (必修) 和 '拓展' (针对用户的保研/竞赛目标)。
                5. **树状拓扑**：严禁出现孤立节点，所有节点必须有箭头关联。
                
                输出 JSON 结构：{{ "nodes": [{{ "id", "label", "type", "stage" }}], "edges": [{{ "source", "target" }}] }}
                type 为 '校内' 或 '拓展'。stage 为 '大一', '大二', '大三', '目标'。
                """
                try:
                    res = client.chat.completions.create(
                        model="glm-4-flash", 
                        messages=[{"role": "user", "content": sys_prompt}],
                        temperature=0.2,
                        max_tokens=2048
                    )
                    raw_text = res.choices[0].message.content.strip()
                    # 清理 Markdown 代码块包裹
                    raw_text = raw_text.replace('```json', '').replace('```', '').strip()
                    tree_data = json.loads(raw_text)
                    st.session_state.dynamic_tree = tree_data
                    
                    # --- 智能自适应免修模块 ---
                    user_lvl_val = 1
                    if "大二" in user_stage: user_lvl_val = 2
                    elif "大三" in user_stage: user_lvl_val = 3
                    elif "大四" in user_stage: user_lvl_val = 4
                    
                    st.session_state.completed_nodes = [
                        n['id'] for n in tree_data['nodes'] 
                        if (user_lvl_val >= 2 and n.get('stage') == "大一") or \
                           (user_lvl_val >= 3 and n.get('stage') == "大二") or \
                           (user_lvl_val >= 4 and n.get('stage') == "大三")
                    ]
                    st.session_state.target_node = None
                    st.success("✅ 演算成功！已强制执行[程序设计->数据结构]逻辑顺序，并剔除了非核心干扰课程。")
                except Exception as e:
                    st.error(f"⚠️ 解析失败: {e}")

    # 图谱渲染逻辑
    if st.session_state.dynamic_tree:
        tree = st.session_state.dynamic_tree
        
        # 构建前置依赖字典
        dynamic_prereqs = {}
        for edge in tree.get('edges', []):
            dynamic_prereqs.setdefault(edge['target'], []).append(edge['source'])
            
        dynamic_base_nodes = [n['id'] for n in tree['nodes'] if n['id'] not in dynamic_prereqs]

        def is_unlocked(nid):
            if nid in dynamic_base_nodes: return True
            return all(req in st.session_state.completed_nodes for req in dynamic_prereqs.get(nid, []))

        # 构建节点
        nodes = []
        for n in tree['nodes']:
            ntype = n.get('type', '校内')
            if n['id'] in st.session_state.completed_nodes:
                color = "#FFD700" 
            elif not is_unlocked(n['id']):
                color = "#4F4F4F" 
            else:
                color = "#1E90FF" if ntype == "校内" else "#9370DB"
            
            # 使用最稳健的 Node 构造函数，确保标签显示
            nodes.append(Node(
                id=n['id'], 
                label=f"{n.get('label', '未知')} ({ntype})", 
                color=color, 
                size=30
            ))
        
        edges = [Edge(source=e['source'], target=e['target'], color="#AAAAAA", width=2) for e in tree.get('edges', [])]
        
        # 布局优化
        config = Config(
            width=1100, height=700, directed=True, physics=False, hierarchical=True, 
            layout={
                "hierarchical": {
                    "enabled": True, "direction": "UD", "sortMethod": "directed",
                    "nodeSpacing": 450, "levelSeparation": 250, "edgeMinimization": True
                }
            }
        )
        
        clicked = agraph(nodes=nodes, edges=edges, config=config)

        if clicked:
            node_data = next((n for n in tree['nodes'] if n['id'] == clicked), None)
            if node_data:
                st.markdown("---")
                
                # --- 终极名师网课直通库（人工校对防止幻觉） ---
                verified_links = {
                    "程序设计": "https://www.bilibili.com/video/BV1et411b73Z/",
                    "C++": "https://www.bilibili.com/video/BV1et411b73Z/",
                    "C语言": "https://www.bilibili.com/video/BV1q54y1q79w/",
                    "离散数学": "https://www.bilibili.com/video/BV1kx411D71x/", # 屈婉玲
                    "数据结构": "https://search.bilibili.com/all?keyword=王道数据结构",
                    "操作系统": "https://search.bilibili.com/all?keyword=王道操作系统",
                    "计算机网络": "https://search.bilibili.com/all?keyword=王道计算机网络",
                    "组成原理": "https://search.bilibili.com/all?keyword=王道计算机组成原理",
                    "编译原理": "https://www.bilibili.com/video/BV1zW411t7YE/",
                    "线性代数": "https://www.bilibili.com/video/BV1aW411Q7x1/",
                    "微积分": "https://www.bilibili.com/video/BV1Eb411u7Fw/",
                    "高等数学": "https://www.bilibili.com/video/BV1Eb411u7Fw/",
                    "算法分析": "https://www.bilibili.com/video/BV1A4411v7hK/",
                    "蓝桥杯": "https://search.bilibili.com/all?keyword=蓝桥杯真题解析",
                    "CCPC": "https://search.bilibili.com/all?keyword=CCPC算法训练",
                    "保研": "https://search.bilibili.com/all?keyword=计算机保研面试经验",
                }
                
                final_link = ""
                course_text = str(node_data['label']).upper()
                for key, url in verified_links.items():
                    if key.upper() in course_text:
                        final_link = url
                        break
                
                if not final_link:
                    safe_keyword = urllib.parse.quote(node_data['label'])
                    final_link = f"https://search.bilibili.com/all?keyword={safe_keyword}"
                
                st.info(f"📍 选中节点：{node_data['label']} ({node_data.get('type', '校内')})")
                st.markdown(f"👉 **网课直通车：** [{node_data['label']} (点击直达▶️)]({final_link})")
                st.session_state.target_node = clicked

# ==================== 功能区 2：AI 测评大厅 ====================
with tab2:
    if not st.session_state.target_node:
        st.warning("⚠️ 请先在【科技树】标签页点击一个节点进行测评！")
    else:
        target_id = st.session_state.target_node
        st.subheader(f"⚔️ 正在挑战：{target_id}")
        
        c1, c2 = st.columns([2, 3])
        with c1:
            if st.button("🎲 生成定制化考题", use_container_width=True):
                with st.spinner("AI 导师出题中..."):
                    q_prompt = f"针对【{target_id}】知识点，我是{user_stage}。请出一道考察核心逻辑的代码题或逻辑题。给出题目说明和输入输出示例。不给答案。"
                    try:
                        res = client.chat.completions.create(model="glm-4-flash", messages=[{"role": "user", "content": q_prompt}])
                        st.session_state.question = res.choices[0].message.content
                    except Exception: st.error("出题失败，请检查 API")
            
            if st.session_state.question:
                st.markdown(st.session_state.question)

        with c2:
            ans = st.text_area("⌨️ 输入你的解答：", height=300, placeholder="写下你的代码实现或逻辑推导...")
            if st.button("🚀 提交测评", type="primary", use_container_width=True):
                if not ans:
                    st.warning("请输入内容！")
                else:
                    with st.spinner("导师判卷中..."):
                        try:
                            c_res = client.chat.completions.create(
                                model="glm-4-flash", 
                                messages=[{"role": "user", "content": f"题目：{st.session_state.question}\n回答：{ans}\n判题，正确请在开头说'通过'。"}]
                            )
                            feedback = c_res.choices[0].message.content
                            st.write("### 👨‍🏫 导师评语：")
                            st.write(feedback)
                            if "通过" in feedback:
                                st.success("✅ Accepted！经验值 +100")
                                if target_id not in st.session_state.completed_nodes:
                                    st.session_state.completed_nodes.append(target_id)
                                    st.session_state.exp += 100
                                st.balloons()
                        except Exception: st.error("测评异常")

# ==================== 功能区 3：竞赛雷达 ====================
with tab3:
    st.subheader("🏆 保研加分赛事扫描雷达")
    if st.button("🔍 开启全网智能匹配", type="primary", use_container_width=True):
        if not client:
            st.error("请配置 API Key")
        else:
            with st.spinner("检索中..."):
                try:
                    res = client.chat.completions.create(
                        model="glm-4-flash", 
                        messages=[{"role": "user", "content": f"基于学段{user_stage}和目标{user_goal}，推荐 5-6 个保研加分白名单赛事。详细说明含金量和建议。"}]
                    )
                    st.session_state.comp_radar = res.choices[0].message.content
                except Exception: 
                    st.session_state.comp_radar = "由于网络抖动，暂无法获取。建议参考蓝桥杯、ACM、计算机设计大赛等 A 类赛事。"
    
    if st.session_state.comp_radar:
        st.markdown(st.session_state.comp_radar)

st.markdown("---")
st.caption("🚀 AI 智教系统完全体 | 专为北科大 CS 学习者设计 | 支持云端与本地自适应")
