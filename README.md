# 智能语音对话助手

本项目是一个来源于[小智xiaozhi-esp32-server](https://github.com/xinnan-tech/xiaozhi-esp32-server)的基于阿里云服务的智能语音对话助手，实现了从语音输入到语音输出的全流程：
> 用户录音 → 语音识别（ASR）→ 大模型生成回复（LLM）→ 语音合成（TTS）→ 播放回复音频

前端使用 Gradio 构建简洁的 Web 界面，后端集成阿里云语音识别、阿里百炼大模型和阿里云语音合成服务，支持实时对话。

## 功能特点
- 🎙️ 语音输入：通过浏览器麦克风录音，支持一键录制和停止。
- 🧠 智能回复：调用阿里百炼大模型（如 Qwen-turbo）生成自然语言回复。
- 🔊 语音输出：将回复文本合成为语音并自动播放。
- 💬 对话历史：界面左侧展示完整的对话记录，用户可随时回顾。
- ⏱️ 音频时长限制：自动检测录音时长，超过 30 秒会提示用户重录。
- 🧪 测试功能：内置测试音频生成函数，方便开发者调试。

## 环境要求
- Python 3.8 或更高版本
- 已开通阿里云相关服务并获取密钥（见下方配置说明）
- 可选：ffmpeg（用于音频格式转换，若不安装则使用默认 PCM 格式）

## 安装步骤
### 1. 克隆代码仓库
```bash
git clone https://github.com/naughtyyou/Intelligent-Voice-Dialogue-System.git
cd <project-folder>
```
### 2. 创建并激活虚拟环境（推荐）
```bash
python -m venv venv
source venv/bin/activate  # Linux/Mac
venv\Scripts\activate     # Windows
```
### 3. 安装依赖包
```bash
pip install -r requirements.txt
```
### 4. 安装 ffmpeg（可选）
音频转换功能依赖 ffmpeg，若未安装，程序会使用原始音频格式（可能影响识别效果）。

Windows：下载 ffmpeg 并添加到系统 PATH。

Linux：sudo apt install ffmpeg

Mac：brew install ffmpeg

## 配置说明
本项目需要您拥有阿里云相关服务的访问权限，请在运行前配置好密钥。
### 获取密钥
### 阿里云语音识别（ASR）和语音合成（TTS）
1. 访问 阿里云智能语音交互控制台，开通服务并创建项目。
2. 获取项目的 Appkey 以及您的 AccessKey ID 和 AccessKey Secret（需拥有 AliyunNLSSpeechFullAccess 权限）。
## 阿里百炼大模型（LLM）
访问 阿里百炼控制台，开通模型服务并获取 API Key。
可使用 qwen-turbo 等模型。
## 修改配置文件
在 unified_processor.py 末尾找到 SAMPLE_CONFIG 字典，将其中的密钥替换为您自己的信息

## 运行方法
在项目目录下执行：
```bash
python gradio_page.py
```
启动成功后，终端会显示本地访问地址：(http://localhost:7860) ，用浏览器打开即可使用。
## 使用说明
### 开始对话
1. 点击 “录制” 按钮开始说话，点击“停止”停止录音并提交处理。
2. 系统会依次执行语音识别、大模型生成、语音合成，并在界面右侧显示回复文本、播放合成语音，同时左侧对话历史会更新。
### 清空对话
点击 “清空对话” 按钮可重置聊天记录。
### 音频时长限制
系统会自动检测录音时长，若超过 30 秒会提示重新录制。
### 状态提示
界面底部的状态栏会显示 “处理中...”、“准备就绪” 或错误信息。

## 项目结构
```text
├── gradio_page.py          # Gradio 前端界面及主逻辑
├── unified_processor.py    # 后端核心处理模块（ASR + LLM + TTS）
├── requirements.txt        # 依赖清单（可选）
└── README.md               # 本文件
```
## 注意事项
1. 网络状况会影响响应速度，请确保服务器能正常访问阿里云 API。
2. 录音环境尽量安静，以提高语音识别准确率。
3. 音频转换依赖 ffmpeg，若未安装，程序会使用原始录音数据（可能因格式不匹配导致识别失败）。建议安装 ffmpeg。
4. 若遇到 asyncio.run () 相关错误，请检查 Gradio 版本是否 ≥ 5.0，推荐使用 Gradio 5.9.1。
5. 部分浏览器可能需要用户与页面交互后才能自动播放音频，可在浏览器设置中开启自动播放权限。

## 常见问题
**Q：录音后没有回复或长时间无响应？**

A：可能是网络问题或密钥配置错误，请检查终端输出的详细日志，确认 ASR、LLM、TTS 的请求是否成功。

**Q：合成的语音无法播放？**
 
 A：请检查浏览器是否允许自动播放音频，部分浏览器需要用户与页面交互后才能播放。可在浏览器设置中开启自动播放权限。

**Q：如何修改使用的模型或音色？**
 
 A：在 SAMPLE_CONFIG 中修改 llm.model 和 tts.voice 字段，具体可选值请参考阿里云官方文档。

**Q：出现 “ASR Token 获取失败” 错误？**
 
 A：请检查 AccessKey ID/Secret 是否正确，并确保账户已开通阿里云智能语音交互服务。
