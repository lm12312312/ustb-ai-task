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

st.set_page_config(
    page_title="AI 智教：北科大 CS 保研全能版", 
    page_icon="🎓", 
    layout="wide",
    initial_sidebar_state="expanded"
)

# 2. 【核心状态管理】初始化 Session State
# 确保在页面刷新时，学习进度、生成的科技树和考题不会丢失
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
# 自动尝试从 Streamlit Cloud 的 Secrets 中读取 ZHIPU_AI_KEY 变量
# 如果你没在后台配置，这里会显示为空，让你在页面上输入
api_key_from_secrets = ""
try:
    api_key_from_secrets = st.secrets.get("ZHIPU_AI_KEY", "")
except Exception:
    pass

# 3. 【侧边栏】智教控制台与学习者画像
with st.sidebar:
    st.title("⚙️ 智教控制台")
    # 优先显示 Secrets 中的 Key，若无则允许手动输入
    user_input_key = st.text_input(
        "🔑 智谱 API Key", 
        value=api_key_from_secrets if api_key_from_secrets else "",
        type="password",
        help="建议在部署后台的 Settings -> Secrets 中配置 ZHIPU_AI_KEY 以免手动输入"
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

# 确定最终使用的 API Key 并初始化客户端
final_key = user_input_key if user_input_key else api_key_from_secrets
client = None
if final_key:
    client = OpenAI(api_key=final_key, base_url="https://open.bigmodel.cn/api/paas/v4")

st.title("🎓 AI 智教：基于北科大方案的全周期路径系统")
st.caption("集成 AI 动态演算、LeetCode 级别判题、保研加分雷达为一体的 CS 学习闭环")

tab1, tab2, tab3 = st.tabs(["🗺️ AI 演算科技树", "⚔️ AI 知识测评 (OJ模式)", "🏆 保研竞赛雷达 (加分专属)"])

# ==================== 功能区 1：AI 动态演算科技树 (核心大脑) ====================
with tab1:
    if st.button("🚀 启动 AI 路径全景演算", type="primary", use_container_width=True):
        if not client:
            st.error("❌ 请先在左侧输入 API Key！(或在管理后台配置 Secrets)")
        else:
            with st.spinner("AI 导师正在结合北科大培养方案演算路径，请稍候..."):
                sys_prompt = f"""你是一个极其严苛且专业的计算机学院教务架构师。
                用户身份：{user_stage}，核心目标：{user_goal}。
                
                【致命约束条件 - 拒绝冗余与重叠】：
                1. 严禁生成重复或高度相似的节点：绝对不要同时出现“程序设计基础”和“C++基础”，必须将其内容合并为一个节点。
                2. 严禁单线串联：生成的图必须具有分叉和层次感。
                3. 严密的先修逻辑：基础课程 source 必须指向进阶目标 target。
                4. 输出纯 JSON 格式：包含 'nodes' (含 id, label, source, stage) 和 'edges'。
                5. 每个 node 的 'stage' 必须是 '大一', '大二', '大三', '拓展' 之一。
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
                    temp_tree = json.loads(raw_text)
                    
                    if 'nodes' in temp_tree and 'edges' in temp_tree:
                        st.session_state.dynamic_tree = temp_tree
                        
                        # 【智能自适应免修模块】
                        # 根据用户填写的年级，自动点亮基础课程，无需重复考核
                        user_lvl_val = 1
                        if "大二" in user_stage: user_lvl_val = 2
                        elif "大三" in user_stage: user_lvl_val = 3
                        elif "大四" in user_stage: user_lvl_val = 4
                        
                        st.session_state.completed_nodes = [
                            n['id'] for n in temp_tree['nodes'] 
                            if (user_lvl_val >= 2 and n.get('stage') == "大一") or \
                               (user_lvl_val >= 3 and n.get('stage') == "大二") or \
                               (user_lvl_val >= 4 and n.get('stage') == "大三")
                        ]
                        st.session_state.target_node = None
                        st.success("✅ 演算成功！已根据你的年级自动点亮了前置技能节点。")
                    else:
                        st.error("AI 生成结果格式不完整，请重试。")
                except Exception as e:
                    st.error(f"⚠️ 解析失败: {e}")

    # 图谱渲染逻辑
    if st.session_state.dynamic_tree:
        tree = st.session_state.dynamic_tree
        
        # 构建前置依赖关系字典，用于判断节点是否解锁
        dynamic_prereqs = {}
        for edge in tree.get('edges', []):
            dynamic_prereqs.setdefault(edge['target'], []).append(edge['source'])
            
        dynamic_base_nodes = [n['id'] for n in tree['nodes'] if n['id'] not in dynamic_prereqs]

        def is_dynamic_unlocked(nid):
            if nid in dynamic_base_nodes: return True
            return all(req in st.session_state.completed_nodes for req in dynamic_prereqs.get(nid, []))

        # 构建 Agraph 节点 UI
        nodes = []
        for n in tree['nodes']:
            src = n.get('source', '校内')
            if n['id'] in st.session_state.completed_nodes:
                color = "#FFD700" # 金色：已点亮
            elif not is_dynamic_unlocked(n['id']):
                color = "#4F4F4F" # 灰色：未解锁
            else:
                color = "#1E90FF" if src == "校内" else "#9370DB" # 蓝色/紫色：当前可学
            
            # 使用换行符增加标签的可读性
            nodes.append(Node(id=n['id'], label=f"{n['label']}\n[{src}]", color=color, size=35))
        
        edges = [Edge(source=e['source'], target=e['target'], color="#AAAAAA") for e in tree.get('edges', [])]
        
        # 【布局极致优化】大幅拉开 nodeSpacing 间距，彻底消除文字重叠
        config = Config(
            width=1100, 
            height=700, 
            directed=True, 
            physics=False, 
            hierarchical=True, 
            layout={
                "hierarchical": {
                    "enabled": True, 
                    "direction": "UD", 
                    "sortMethod": "directed",
                    "nodeSpacing": 450,      # 水平间距：极宽，防止长文字碰撞
                    "levelSeparation": 250,  # 垂直间距：大幅拉开层级
                    "edgeMinimization": True
                }
            }
        )
        
        clicked = agraph(nodes=nodes, edges=edges, config=config)

        if clicked:
            node_data = next((n for n in tree['nodes'] if n['id'] == clicked), None)
            if node_data:
                st.markdown("---")
                
                # 【千万级名师库】人工校验的顶级 B 站直达链接
                verified_direct_links = {
                    "程序设计基础": "https://www.bilibili.com/video/BV1et411b73Z/",
                    "C++": "https://www.bilibili.com/video/BV1et411b73Z/",
                    "C语言": "https://www.bilibili.com/video/BV1q54y1q79w/",
                    "离散数学": "https://www.bilibili.com/video/BV1kx411D71x/", # 屈婉玲教授经典版
                    "数据结构": "https://www.bilibili.com/video/BV1JW411i731/",
                    "操作系统": "https://www.bilibili.com/video/BV1YE411D7nH/",
                    "计算机网络": "https://www.bilibili.com/video/BV19E411D78Q/",
                    "计算机组成": "https://www.bilibili.com/video/BV1c4411w7nd/",
                    "编译原理": "https://www.bilibili.com/video/BV1zW411t7YE/",
                    "线性代数": "https://www.bilibili.com/video/BV1aW411Q7x1/",
                    "微积分": "https://www.bilibili.com/video/BV1Eb411u7Fw/",
                    "概率论": "https://www.bilibili.com/video/BV1ot411y7mU/",
                    "人工智能": "https://www.bilibili.com/video/BV1Pa411X76s/",
                    "算法竞赛": "https://www.bilibili.com/video/BV1A4411v7hK/",
                    "蓝桥杯": "https://search.bilibili.com/all?keyword=蓝桥杯真题精讲",
                    "CCPC": "https://search.bilibili.com/all?keyword=CCPC算法竞赛入门",
                }
                
                final_link = ""
                course_text = (node_data['label']).upper()
                for key, url in verified_direct_links.items():
                    if key.upper() in course_text:
                        final_link = url
                        break
                
                if not final_link:
                    safe_keyword = urllib.parse.quote(node_data['label'])
                    final_link = f"https://search.bilibili.com/all?keyword={safe_keyword}"
                
                st.info(f"📍 选中节点：{node_data['label']}")
                st.markdown(f"👉 **锁定目标！推荐网课直通车：** [{node_data['label']} (点击直达▶️)]({final_link})")
                
                if clicked in st.session_state.completed_nodes:
                    st.success("🎉 该节点已点亮掌握！")
                    st.write("如果你想重新考核获取额外经验值，也可以直接前往测评大厅。")
                
                st.session_state.target_node = clicked

# ==================== 功能区 2：AI 知识测评 (OJ 模式) ====================
with tab2:
    if not st.session_state.target_node:
        st.warning("⚠️ 请先在【科技树】标签页点击你想要挑战的节点！")
    else:
        target_id = st.session_state.target_node
        st.subheader(f"⚔️ 正在进行【{target_id}】的导师考核")
        
        col_q, col_a = st.columns([2, 3])
        
        with col_q:
            if st.button("🎲 抽取定制化考题", use_container_width=True):
                with st.spinner("AI 导师正在结合你的背景出题..."):
                    q_prompt = f"针对【{target_id}】知识点，我是{user_stage}，目标是{user_goal}。请出一道深度理解题或 LeetCode 风格算法题，给出题目描述、输入输出示例。不给答案。"
                    try:
                        res = client.chat.completions.create(
                            model="glm-4-flash", 
                            messages=[{"role": "user", "content": q_prompt}]
                        )
                        st.session_state.question = res.choices[0].message.content
                    except Exception:
                        st.error("出题失败，请检查 API 设置。")
            
            if st.session_state.question:
                st.markdown("### 📝 题目详情：")
                st.markdown(st.session_state.question)

        with col_a:
            ans = st.text_area("⌨️ 输入你的代码实现或逻辑解析：", height=300, placeholder="在此编写你的答案...")
            if st.button("🚀 提交并评测", type="primary", use_container_width=True):
                if not ans:
                    st.warning("请输入答案后再提交！")
                else:
                    with st.spinner("导师正在严密审阅你的逻辑..."):
                        check_prompt = f"题目：{st.session_state.question}\n我的回答：{ans}\n请针对我的逻辑进行专业判题。如果基本正确请在开头明确说'通过'，否则明确说'不通过'。"
                        try:
                            c_res = client.chat.completions.create(
                                model="glm-4-flash", 
                                messages=[{"role": "user", "content": check_prompt}]
                            )
                            feedback = c_res.choices[0].message.content
                            st.markdown("### 👨‍🏫 导师评语：")
                            st.write(feedback)
                            
                            if "通过" in feedback and "不通过" not in feedback:
                                st.success("✅ Accepted！该节点已掌握，经验值 +100")
                                if target_id not in st.session_state.completed_nodes:
                                    st.session_state.completed_nodes.append(target_id)
                                    st.session_state.exp += 100
                                st.balloons()
                        except Exception:
                            st.error("测评异常，请重试。")

# ==================== 功能区 3：保研竞赛雷达 (加分专属) ====================
with tab3:
    st.subheader("🏆 保研加分赛事扫描雷达")
    st.info("AI 会根据你的年级和目标，从教育部白名单及高校保研加分库中筛选出最适合你的赛事。")
    
    if st.button("🔍 开启全网扫描与智能匹配", type="primary", use_container_width=True):
        if not client:
            st.error("请先配置 API Key！")
        else:
            with st.spinner("正在检索最新赛事动态..."):
                try:
                    radar_prompt = f"基于身份{user_stage}和目标{user_goal}，推荐 5-6 个保研加分白名单赛事。详细说明其含金量、加分权重及备赛建议。"
                    res = client.chat.completions.create(
                        model="glm-4-flash", 
                        messages=[{"role": "user", "content": radar_prompt}]
                    )
                    st.session_state.comp_radar = res.choices[0].message.content
                except Exception:
                    st.session_state.comp_radar = """
                    ### 🏆 本地核心赛事库 (保研加分 A 类)
                    1. **蓝桥杯全国软件大赛**：省一及以上对保研非常有帮助。
                    2. **ACM-ICPC / CCPC**：算法天花板，拿奖即意味着保研免试。
                    3. **中国大学生计算机设计大赛**：作品类竞赛，门槛适中，含金量稳定。
                    4. **“挑战杯”系列竞赛**：含金量极高，综合实力体现。
                    5. **“互联网+”大学生创新创业大赛**：目前国内最大规模、加分最显著的赛事。
                    """
    
    if st.session_state.comp_radar:
        st.markdown(st.session_state.comp_radar)

st.markdown("---")
st.caption("🚀 AI 智教系统 V2.0 | 专为北科大 CS 学习者打造 | 支持 GitHub / Streamlit Cloud 一键部署")
