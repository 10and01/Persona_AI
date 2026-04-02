# Persona AI

一个基于 Python 的 Persona/Memory 引擎项目，包含：
- 核心能力：画像提取、置信度评估、隐私治理、记忆生命周期管理
- 测试：Python 单元测试
- Web 可视化：Next.js 前端（位于 web 目录）

## 项目结构

- `src/persona_ai/`：核心业务代码
- `tests/`：测试用例
- `docs/`：运维与集成文档
- `openspec/`：规格与变更记录
- `web/`：前端可视化与 API 路由

## 环境要求

- Python 3.11+
- Node.js 18+（用于 web 前端）

## 快速开始

### 1) Python 部分

```bash
python -m venv .venv
. .venv/Scripts/activate  # Windows PowerShell 可改用 .venv\\Scripts\\Activate.ps1
pip install -e .
pytest
```

### 2) Web 部分

```bash
cd web
npm install
npm run dev
```

默认启动后可访问：
- http://localhost:3000

## 关键文档

- `docs/host-integration-guide.md`
- `docs/operations-runbook.md`
- `docs/release-baseline-checklist.md`

## 备注

- 本仓库已通过根目录 `.gitignore` 忽略 Python/Node 常见产物与本地环境文件。
- 如需提交示例环境变量，请新增 `.env.example` 并避免提交真实密钥。
