# 自我迭代可视化

上传 CSV 并描述需求后，系统会自动 **编码 → 跑图 → 审查**，最多 3 轮。结束后可人工选择满意或不满意；不满意可填写改进建议继续迭代。生成的图片可在页面下载。

## 环境要求

- Python 3.11+（需能使用 `pandas`、`matplotlib`）
- Node.js 18+（用于前端）
- 大模型 API Key（默认对接智谱 GLM，兼容 OpenAI 接口）

## 配置密钥

`.env` 不会进入 Git。克隆后在本目录执行：

```powershell
copy .env.example .env
```

编辑 `.env`，至少填写：

```
OPENAI_API_KEY=你的密钥
OPENAI_BASE_URL=https://open.bigmodel.cn/api/paas/v4
OPENAI_MODEL=glm-4.6v
OPENAI_VISION_MODEL=glm-4.6v
PYTHON_BIN=python
```

国内智谱用上面的 `BASE_URL`；国际 Z.AI 可改为 `https://api.z.ai/api/paas/v4`。未配置 Key 时，创建作业会返回错误，不会假装出图。

## 安装

```powershell
cd backend
python -m pip install -r requirements.txt

cd ..\frontend
npm install
```

## 运行

开两个终端。

后端（`webapp/backend`）：

```powershell
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

前端（`webapp/frontend`）：

```powershell
npm run dev
```

浏览器打开 http://localhost:5173/  
前端会把 `/api` 和 `/runs` 代理到 `8000`。

## 使用

1. 填写需求（例如：各区域季度销售额趋势图）
2. 选择 CSV 文件
3. 点击「开始自动迭代」
4. 等待各版本图表与审查结果
5. 选择「满意」结束，或「不满意」输入建议后再迭
6. 点击「下载图片」保存 PNG

## 目录说明

```
backend/app/          FastAPI：作业、编码、执行、审查
backend/prompts/      编码员 / 审查员提示词
backend/runs/         每次作业的 CSV 副本、脚本、图片、state.json（不入库）
frontend/              Vite + React 页面
.env.example           环境变量模板
```

`backend/runs/` 是本地运行产物，默认被 `.gitignore` 忽略。删除某个作业文件夹只丢掉那次历史，不影响代码。

## 注意

- 不要提交 `.env`
- 生成的 Python 会在作业目录下以 `MPLBACKEND=Agg` 执行；危险操作（如 `os.system`）会被拒绝
- 审查依赖带视觉的模型；JSON 解析失败时本轮记为未通过，可人工继续
