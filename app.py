import streamlit as st
import pandas as pd
import base64
import json
import os
from datetime import datetime
from io import BytesIO
from PIL import Image
from openai import OpenAI

# ================= 1. 页面基础设置 =================
st.set_page_config(page_title="专属饮食热量管家", page_icon="🥗", layout="centered")
DATA_FILE = "food_log.csv"
PROFILE_FILE = "user_profile.json"

# 初始化读取历史饮食记录
if os.path.exists(DATA_FILE):
    df_log = pd.read_csv(DATA_FILE)
else:
    df_log = pd.DataFrame(columns=[
        "日期", "餐别", "菜品名称", "热量_kcal", "蛋白质_g", "碳水_g", "脂肪_g", "做法标签", "健康评分", "高质平替建议"
    ])

# 初始化读取个人身高体重档案
default_profile = {"height": 162, "weight": 55.0, "age": 24, "activity": 1.375, "deficit": 300}
if os.path.exists(PROFILE_FILE):
    with open(PROFILE_FILE, "r", encoding="utf-8") as f:
        profile = json.load(f)
else:
    profile = default_profile

# ================= 2. 侧边栏：个人档案与 API 设置 =================
with st.sidebar:
    st.header("⚙️ 个人档案与设置")
    api_key = st.text_input("填入智谱 API Key", value="8dba9f1fbc294ffba010eb7fb89a070e.v8kjAUDAzuHdNrsS", type="password")
    
    st.subheader("📏 身体数据（自动算每日额度）")
    height = st.number_input("身高 (cm)", value=profile["height"], min_value=120, max_value=220)
    weight = st.number_input("当前体重 (kg)", value=profile["weight"], min_value=30.0, max_value=150.0, step=0.5)
    age = st.number_input("年龄", value=profile["age"], min_value=12, max_value=80)
    activity_map = {
        "久坐办公/极少运动": 1.2,
        "轻度活动（每周运动1-3次或常散步）": 1.375,
        "中度运动（每周慢跑/健身3-5次）": 1.55
    }
    act_label = st.selectbox("日常活动量", list(activity_map.keys()), index=1)
    deficit = st.slider("每日减脂热量缺口 (大卡)", 0, 500, profile["deficit"], step=50, help="想保持体重选0，温和减脂建议选300")

    if st.button("💾 保存个人档案"):
        profile = {"height": height, "weight": weight, "age": age, "activity": activity_map[act_label], "deficit": deficit}
        with open(PROFILE_FILE, "w", encoding="utf-8") as f:
            json.dump(profile, f)
        st.success("档案已保存！")

# 用 Mifflin-St Jeor 公式计算女性基础代谢与每日目标热量
bmr = int(10 * weight + 6.25 * height - 5 * age - 161)
tdee = int(bmr * activity_map[act_label])
daily_target = max(1200, tdee - deficit)

# ================= 3. 顶部看板：今日热量进度环 =================
st.title("🥗 专属每日饮食热量管家")
today_str = datetime.now().strftime("%Y-%m-%d")
today_df = df_log[df_log["日期"] == today_str]
today_Intake = int(today_df["热量_kcal"].sum()) if not today_df.empty else 0
remaining_kcal = daily_target - today_Intake

col1, col2, col3 = st.columns(3)
col1.metric("🎯 今日目标额度", f"{daily_target} kcal", f"总消耗约 {tdee} kcal")
col2.metric("🍽️ 今日已摄入", f"{today_Intake} kcal")
col3.metric("🔋 今日剩余可吃", f"{remaining_kcal} kcal", delta="额度充足" if remaining_kcal >= 0 else "今日已超标", delta_color="normal" if remaining_kcal >= 0 else "inverse")

progress_val = min(1.0, today_Intake / daily_target) if daily_target else 0
st.progress(progress_val)

# ================= 4. 核心功能区：三大标签页 =================
tab1, tab2, tab3 = st.tabs(["📸 拍照记一餐", "📈 每日趋势图表", "🏆 月度总结与推荐"])

with tab1:
    st.subheader("第一步：拍下你的食物")
    uploaded_file = st.file_uploader("手机端点击可直接调用【拍照】或从相册选图", type=["jpg", "jpeg", "png", "webp"])
    
    st.subheader("第二步：3 秒点选隐藏细节（不打字也算得准）")
    c1, c2 = st.columns(2)
    with c1:
        meal_type = st.radio("餐别", ["早餐", "午餐", "晚餐", "加餐/夜宵"], horizontal=True)
        cook_style = st.radio("烹饪做法与油量", ["自制少油/清淡", "食堂/家常正常油", "外卖/餐馆重油", "油炸/烧烤/浓油赤酱"])
    with c2:
        portion = st.select_slider("实际吃了图中的多少？", options=["尝几口(25%)", "吃了一半(50%)", "大半份(75%)", "全吃完(100%)"], value="全吃完(100%)")
        extra_tags = st.multiselect("特殊排雷细节（可多选）", ["拌了浓酱/麻酱/红油", "喝了肉汤/浓汤", "已去皮/撇去浮油", "主食只吃了一半"])
    
    extra_note = st.text_input("补充说明（选填，比如：里面包的是猪肉馅）", placeholder="不填也可以，直接点下方按钮")

    if uploaded_file is not None:
        img = Image.open(uploaded_file)
        st.image(img, caption="待分析的餐食照片", use_container_width=True)
        
        if st.button("✨ 立即让 AI 算热量并自动存档", type="primary", use_container_width=True):
            if not api_key:
                st.error("请先在左侧边栏填入你的智谱 API Key！")
            else:
                with st.spinner("正在识别中国菜品并结合油量、份量修正热量..."):
                    # 压缩图片并转为 Base64
                    img.thumbnail((1024, 1024))
                    buffered = BytesIO()
                    img.convert("RGB").save(buffered, format="JPEG", quality=85)
                    img_base64 = base64.b64encode(buffered.getvalue()).decode("utf-8")

                    prompt_text = f"""
                    你是一位精通中国家常菜、地方小吃与外卖营养学的高级注册营养师。
                    请分析这张食物照片，并严格结合以下用户实际就餐细节修正热量估算：
                    - 烹饪与油量：{cook_style}
                    - 实际吃下比例：{portion}
                    - 特殊细节：{', '.join(extra_tags) if extra_tags else '无'}
                    - 额外说明：{extra_note if extra_note else '无'}

                    请只输出严格的 JSON 格式（不要包含 markdown 代码块符号），包含以下字段：
                    {{
                        "dish_name": "识别出的全部菜品名称及预估实际吃下的克重（如：宫保鸡丁约150g + 米饭150g）",
                        "calories": 修正后的实际摄入总热量整数(kcal),
                        "protein": 蛋白质克数整数(g),
                        "carbs": 碳水化合物克数整数(g),
                        "fat": 脂肪克数整数(g),
                        "score": 健康评分整数(1到10分),
                        "reason": "一句话解释为什么是这个热量（指出隐藏油量或主食占比）",
                        "better_food": "针对这顿饭的营养短板，推荐1-2种下顿可吃的高质量食物或平替做法"
                    }}
                    """
                    try:
                        client = OpenAI(api_key=api_key, base_url="https://open.bigmodel.cn/api/paas/v4/")
                        response = client.chat.completions.create(
                            model="glm-4v-flash",
                            messages=[{
                                "role": "user",
                                "content": [
                                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{img_base64}"}},
                                    {"type": "text", "text": prompt_text}
                                ]
                            }],
                            temperature=0.2
                        )
                        raw_text = response.choices[0].message.content.strip()
                        raw_text = raw_text.replace("```json", "").replace("```", "").strip()
                        result = json.loads(raw_text)

                        # 展示识别结果
                        st.success(f"✅ 已识别并自动存档：**{result['dish_name']}**")
                        r1, r2, r3, r4 = st.columns(4)
                        r1.metric("本餐热量", f"{result['calories']} kcal")
                        r2.metric("蛋白质", f"{result['protein']} g")
                        r3.metric("碳水", f"{result['carbs']} g")
                        r4.metric("脂肪", f"{result['fat']} g")
                        st.info(f"💡 **热量拆解：** {result['reason']}\n\n🥦 **高质量食物建议：** {result['better_food']}")

                        # 写入 CSV 存档
                        new_row = pd.DataFrame([{
                            "日期": today_str,
                            "餐别": meal_type,
                            "菜品名称": result["dish_name"],
                            "热量_kcal": result["calories"],
                            "蛋白质_g": result["protein"],
                            "碳水_g": result["carbs"],
                            "脂肪_g": result["fat"],
                            "做法标签": f"{cook_style}|{portion}",
                            "健康评分": result["score"],
                            "高质平替建议": result["better_food"]
                        }])
                        df_updated = pd.concat([df_log, new_row], ignore_index=True)
                        df_updated.to_csv(DATA_FILE, index=False, encoding="utf-8-sig")
                    except Exception as e:
                        st.error(f"识别出错，请检查 API Key 是否正确。错误详情：{e}")

with tab2:
    st.subheader("📊 每日热量摄入趋势图")
    if df_log.empty:
        st.info("还没有饮食记录哦，先去第一个标签页拍张照试试吧！")
    else:
        daily_summary = df_log.groupby("日期")[["热量_kcal", "蛋白质_g", "碳水_g", "脂肪_g"]].sum().reset_index()
        daily_summary["目标上限"] = daily_target
        st.line_chart(daily_summary.set_index("日期")[["热量_kcal", "目标上限"]])
        
        st.subheader("🥩 每日三大营养素摄入结构 (克)")
        st.bar_chart(daily_summary.set_index("日期")[["蛋白质_g", "碳水_g", "脂肪_g"]])

        st.subheader("📝 历史饮食明细表")
        st.dataframe(df_log.iloc[::-1], use_container_width=True)

with tab3:
    st.subheader("🏆 月度饮食复盘与高质量食谱推荐")
    if len(df_log) == 0:
        st.info("积累几顿饮食记录后，即可在这里一键生成月度营养总结！")
    else:
        avg_kcal = int(df_log.groupby("日期")["热量_kcal"].sum().mean())
        avg_protein = int(df_log.groupby("日期")["蛋白质_g"].sum().mean())
        st.write(f"目前已记录 **{df_log['日期'].nunique()}** 天，日均摄入 **{avg_kcal} kcal**（目标 {daily_target} kcal），日均蛋白质 **{avg_protein} g**。")
        
        if st.button("🤖 生成专属月度营养诊断与高质量食物清单"):
            if not api_key:
                st.error("请先在左侧边栏填入 API Key！")
            else:
                with st.spinner("正在汇总历史账单并生成定制营养方案..."):
                    recent_records = df_log.tail(60).to_dict(orient="records")
                    summary_prompt = f"""
                    用户档案：身高{height}cm，体重{weight}kg，每日目标热量{daily_target}kcal。
                    近期饮食记录：{json.dumps(recent_records, ensure_ascii=False)}
                    请为她生成一份温暖、好懂的【月度饮食总结与下月高质量食物推荐】：
                    1. 找出导致她热量容易超标的 2-3 个“热量刺客”或饮食习惯盲区；
                    2. 评估她的蛋白质是否达标；
                    3. 结合她平时爱吃的菜系口味，推荐 5 种适合她下个月常吃的“高饱腹感、高蛋白、低热量”的高质量具体食物（包含外卖/食堂怎么点）。
                    """
                    client = OpenAI(api_key=api_key, base_url="https://open.bigmodel.cn/api/paas/v4/")
                    res = client.chat.completions.create(
                        model="glm-4-flash",
                        messages=[{"role": "user", "content": summary_prompt}]
                    )
                    st.markdown(res.choices[0].message.content)