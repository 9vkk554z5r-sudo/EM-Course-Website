# EM Course Website

## 本地运行

```powershell
python -m pip install -r requirements.txt
python app.py
```

浏览器访问 <http://localhost:5001>。首次启动会创建管理员账号 `admin / admin123`，登录后请立即修改默认密码。

## 脱离 Codex 独立调用模型

网站直接通过 HTTP 调用配置的 LLM 网关，不依赖 Codex。可选择以下任一种配置方式：

1. 登录管理员后台，打开“API Key 管理”，填写端点、模型编码、部署节点与 API Key，并点击“测试连接”。
2. 复制 `.env.example` 为 `.env`，设置 `LLM_API_ENDPOINT`、`LLM_API_KEY`、`LLM_MODEL` 等环境变量；启动时会自动加载。环境变量优先于数据库配置。

请勿把真实 API Key 提交到 Git。`LLM_API_STYLE=auto` 会先尝试标准 Chat Completions 格式；对于 `/start` 网关，在接口返回参数格式错误时自动尝试 Start 格式。

## 文献检索与知识图谱

- 文献元数据、被引次数和参考文献列表来自 OpenAlex。
- 图中的箭头只由 OpenAlex `referenced_works` 生成，不会把“主题相似”伪装为引用关系。
- 在“文献引用星云图”中可按关键词或 DOI 检索。检索结果会同步到本地数据库，之后首页图谱可直接读取。
- DOI 查询会同时扩展该论文的参考文献和引用它的论文；关键词查询会补充结果之间共享的高频参考文献，以形成可核验的连接。

建议设置 `OPENALEX_EMAIL`，以使用 OpenAlex polite pool。
