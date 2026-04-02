# 🛡️ 基于 NVIDIA NemoClaw 的高安全 AI 自动化矩阵 (v2.1)
**项目目标**：利用企业级沙盒技术构建“零泄露”风险的 AI 资讯自动化系统。
**技术核心**：NemoClaw Sandbox (内核级隔离) + OpenShell Runtime (安全环境) + HITL (人机回路)。

---

## 一、 核心架构图 (System Architecture)

本方案通过 NVIDIA NemoClaw 在本地 Mac mini 上建立一个“安全隔离区”，确保所有 Agent 操作都在受控容器内执行。

| 组件 | 引擎/工具 | 安全职能 | 成本 (Monthly) |
| :--- | :--- | :--- | :--- |
| **感知与抓取** | Gemini 3 Flash API | 全网资讯采集、长文本初筛，利用 2M 上下文。 | **$0** (Free Tier) |
| **安全沙盒** | **NVIDIA NemoClaw** | **核心容器**：在 OpenShell 环境中运行，强制 Landlock 文件隔离。 | **$0** (NVIDIA 开源) |
| **文案生成** | Claude 4.6 (Pro) | 结合风格文件润色。数据发送前经过本地脱敏。 | **$0** (已购 Pro) |
| **中控与审批** | Claude Dispatch | 手机端指令确认、文案微调、下达 Commit 指令。 | **受控** (单次对话) |
| **发布防线** | GitHub Environments | CI/CD 自动部署流程中的最后一道人工确认闸门。 | **$0** (GitHub 免费) |

---

## 二、 隐私泄露排除机制 (Privacy Guardrails)

### 1. 本地脱敏规则 (`redaction_rules.json`)
在数据离开本地环境发往云端 LLM 前，NemoClaw 会强制执行正则表达式匹配：
- **API 密钥**：自动遮蔽 `sk-`, `ghp_` 等开头的字符串。
- **身份信息**：替换 `Rui Zhang`, `USC`, `University of Southern California` 为占位符。
- **本地路径**：将 `/Users/ruizhang/...` 统一重写为虚拟路径。

### 2. 内核级沙盒 (Sandboxed Execution)
- **Landlock 隔离**：Agent 只能读写被授权的 `/sandbox` 目录，无法触碰你的作业、照片或系统配置。
- **网络白名单**：仅允许访问指定的抓取目标（如 ArXiv, GitHub），禁止向未知地址发送数据。

---

## 三、 全链路操作流程 (End-to-End Workflow)

1. **[自动]** NemoClaw 调用 Gemini 抓取过去 24h 的 AI 论文并提炼摘要。
2. **[安全]** 本地隐私路由器扫描摘要，确保没有抓取到敏感的内网信息。
3. **[润色]** 干净的数据传给 Claude，Claude 生成适配 LinkedIn 的专业文案。
4. **[确认]** Claude 通过 Dispatch 发送到你手机。你回复 `OK` 后，NemoClaw 执行 `git push`。
5. **[终审]** GitHub 弹出部署申请，你在 GitHub App 点击 `Approve`，网站正式更新。

---

## 四、 简历描述参考 (Resume Bullet Points)

> **"Implemented a secure AI content pipeline using NVIDIA NemoClaw to automate tech-blogging with zero-trust architecture."**
> - **Security**: Leveraged **OpenShell Runtime** and **Landlock kernel isolation** to create a sandboxed environment for autonomous agents.
> - **Optimization**: Integrated **Gemini 3 Flash** and **Claude 4.6** in a multi-model orchestration, reducing inference costs while maintaining high-fidelity output.
> - **Governance**: Established a **Human-in-the-loop (HITL)** approval workflow via GitHub Environments and Claude Dispatch.

---

## 五、 附录：NemoClaw 快速配置参考
```bash
# 安装 NemoClaw 插件
curl -fsSL [https://www.nvidia.com/nemoclaw.sh](https://www.nvidia.com/nemoclaw.sh) | bash

# 初始化安全沙盒
nemoclaw onboard

# 配置隐私脱敏黑名单
cat > redaction_rules.json <<EOF
{
  "patterns": ["sk-.*", "Rui Zhang", "USC", "/Users/.*"],
  "placeholder": "[SECURE_DATA]"
}
EOF