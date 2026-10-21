# 一餐 · Food tracker

安卓优先的 Streamlit 餐食记录应用。拍照 / 相册 → 自动识别 → 核对菜品和食用比例 → 确认保存。

## Supabase 配置

1. 到 https://supabase.com/dashboard 创建项目，自行保管数据库密码。
2. 在项目的 SQL Editor 中新建查询，粘贴本仓库 `supabase_setup.sql` 的全部内容并运行。
3. 在项目的 Connect / Project Settings / API 页面复制 Project URL 和 **publishable key**（或旧版 anon key）。不要使用 secret / service_role 密钥，后者会绕过行级权限。
4. 在 Streamlit 应用右下角 Manage app → Settings → Secrets 中，按 `secrets.example.toml` 配置。原有配置应保留；填写实际值后保存。
5. 在 Supabase Authentication → Users → Add user → Create new user 为自己和朋友分别建立账号；各自设置不同邮箱和密码。管理员不要把密码发到聊天或 GitHub。可由每位使用者在场分别输入自己的密码。若使用邀请 / 密码重置邮件，需另行接入回调设置密码页面；本版登录表单不处理邮件回调。
6. 回到应用刷新，分别登录。先用两份测试账号验证：A 保存一餐；B 登录后应看不到 A 的餐食和设置；A 再次登录应能找回记录。

数据库未配置时仅开放会话体验模式。体验记录不会自动迁移到正式账号，可在「饮食记录」中导出 CSV 备份。旧版全局 CSV / 档案不会自动分配给任何账号，避免误把某人的记录分给他人。

## 安卓快捷入口

在 Chrome 中打开 https://my-friend-diet.streamlit.app/ ，点击右上角 ⋮ → 添加到主屏幕（部分版本为「安装和创建快捷方式」）。这会创建桌面入口，仍依赖浏览器和网络，不是原生 APK，也不支持离线。

「直接拍照」使用相机权限，可切换前后摄像头。若微信内置浏览器不能调用相机，请在 Chrome 中打开并允许相机权限；也可使用「从相册选图」。本次桌面验证不能代替安卓真机相机验证。

## 数据与 AI

- 用 Supabase Auth 验证账号，按 user_id + 数据库 RLS 隔离餐食与设置。账号客户端仅保存在单个页面会话中，不共享缓存。刷新或关闭页面后可能需要重新登录。
- 不存储照片，仅向智谱发送去除 EXIF 后的压缩 JPEG；确认后只保存菜品、营养数值和日期。
- 图片模型默认 `glm-4.6v-flash`（支持 Base64），可在 Secrets 中修改。无法识别 / 非食物 / 网络超时 / 格式异常不会写入餐食。
- 同一张图在页面交互时不重复调用；主动点「重新识别」才会再次调用。保存使用固定 UUID 去重，成功后清空本餐并刷新看板。
- 菜品数值为照片中完整一份的估算。调整菜品卡片中的克重会自动按原估算比例换算营养；详细编辑表可独立修改各项数值。食用比例统一缩放最终营养数值。
- 月度回顾只使用所选月份的记录。记录日均值不把漏记天数当成零摄入。
- 每日目标由本人设置；本版不再默认按女性身体数据自动计算。
- AI 结果仅为目测估算，识别把握为模型自评。未上传用户餐食进行自动化测试。

## 本地运行与验证

```shell
python -m pip install -r requirements.txt
python -m streamlit run app.py
python -m unittest test_tracker -v
```

本地配置写到 `.streamlit/secrets.toml`，不要提交。SQL 的实际 RLS 以及跨设备持久保存需在配置真实项目后执行双账号验收。
