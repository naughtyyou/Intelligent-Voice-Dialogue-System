import json
import asyncio
import wave
import io
import uuid
import hmac
import hashlib
import base64
import requests
from urllib import parse
import time
from datetime import datetime, timezone
import aiohttp
import traceback
import math
import struct
import random

class ASRProvider:
    def __init__(self, config):
        self.config = config
        self.access_key_id = config.get('access_key_id')
        self.access_key_secret = config.get('access_key_secret')
        self.appkey = config.get('appkey')
        self.token_url = "https://nls-meta.cn-shanghai.aliyuncs.com"
        self.asr_url = "https://nls-gateway.cn-shanghai.aliyuncs.com/stream/v1/asr"

    class AccessToken:
        def __init__(self, access_key_id, access_key_secret):
            self.access_key_id = access_key_id
            self.access_key_secret = access_key_secret
            self.token = None
            self.expire_time = 0

        def get_token(self):
            if time.time() < self.expire_time and self.token:
                return self.token
                
            # 获取阿里云 ASR Token
            nonce = str(uuid.uuid4())
            timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
            
            params = {
                "AccessKeyId": self.access_key_id,
                "Action": "CreateToken",
                "Format": "JSON",
                "SignatureMethod": "HMAC-SHA1",
                "SignatureNonce": nonce,
                "SignatureVersion": "1.0",
                "Timestamp": timestamp,
                "Version": "2019-02-28"
            }
            
            # 构造规范化请求字符串
            sorted_params = sorted(params.items())
            canonicalized_query_string = "&".join(
                [f"{parse.quote(k, safe='')}={parse.quote(v, safe='')}" for k, v in sorted_params]
            )
            
            string_to_sign = "GET&%2F&" + parse.quote(canonicalized_query_string, safe="~")
            
            sign_key = f"{self.access_key_secret}&".encode('utf-8')
            h = hmac.new(sign_key, string_to_sign.encode('utf-8'), hashlib.sha1)
            signature = base64.b64encode(h.digest()).decode('utf-8')
            
            params.update({"Signature": signature})
            url = "https://nls-meta.cn-shanghai.aliyuncs.com/"
            
            try:
                print(f"[DEBUG] 获取ASR Token: URL={url}, params={params}")
                response = requests.get(url, params=params, timeout=10)
                print(f"[DEBUG] ASR Token响应: {response.status_code}, {response.text}")
                
                if response.status_code == 200:
                    result = response.json()
                    self.token = result["Token"]["Id"]
                    self.expire_time = time.time() + 1800 - 60
                    print(f"[DEBUG] 获取ASR Token成功: {self.token}, 过期时间: {self.expire_time}")
                    return self.token
                else:
                    print(f"[ERROR] 获取ASR Token失败: HTTP {response.status_code} - {response.text}")
            except Exception as e:
                print(f"[ERROR] 获取ASR Token异常: {str(e)}")
                traceback.print_exc()
            
            return None

    async def speech_to_text(self, audio_data, session_id):
        """调用阿里云 ASR API 进行语音识别"""
        token = self.AccessToken(self.access_key_id, self.access_key_secret).get_token()
        if not token:
            print("[ERROR] 无法获取有效的ASR Token")
            return None, "获取ASR Token失败"
        
        # 确保转换参数与ASR接口要求一致
        audio_data = convert_audio(
            audio_data,
            target_sample_rate=16000,
            target_channels=1,
            target_bits=16
        )
        
        url = f"{self.asr_url}?appkey={self.appkey}&token={token}&format=pcm&sample_rate=16000&channels=1&bits=16"
        headers = {
            "Content-Type": "application/octet-stream",
            "X-NLS-Token": token,
            "X-NLS-Session-Id": session_id
        }
        
        try:
            print(f"[DEBUG] 发送ASR请求: URL={url}, 音频长度={len(audio_data)}字节")
            async with aiohttp.ClientSession() as session:
                # 确保使用POST方法发送ASR请求
                async with session.post(url, data=audio_data, headers=headers) as response:
                    raw_response = await response.text()
                    print(f"[DEBUG] ASR原始响应: {raw_response}")
                    if response.status == 200:
                        result = await response.json()
                        if result.get("status") == 20000000:
                            if result.get("result"):
                                print(f"[DEBUG] ASR识别成功: {result['result']}")
                                return result["result"], None
                            print(f"[WARNING] ASR识别返回空结果，完整响应: {result}")
                            return "", "ASR返回空结果"
                        else:
                            error_msg = f"ASR识别失败: {result.get('message', '未知错误')} (状态码: {result.get('status')})"
                            print(f"[ERROR] {error_msg}")
                            return None, error_msg
                    else:
                        error_msg = f"ASR请求失败: HTTP {response.status} - {raw_response}"
                        print(f"[ERROR] {error_msg}")
                        return None, error_msg
        except Exception as e:
            error_msg = f"ASR请求异常: {str(e)}"
            print(f"[ERROR] {error_msg}")
            traceback.print_exc()
            return None, error_msg
        
class AliBLProvider:
    def __init__(self, config):
        self.access_key_id = config.get('access_key_id')
        self.access_key_secret = config.get('access_key_secret')
        self.api_key = config.get('api_key')
        self.api_url = "https://dashscope.aliyuncs.com/api/v1/services/aigc/text-generation/generation"
        self.model = config.get('model', 'qwen-turbo')

    async def generate_response(self, messages):
        """调用千问大模型 API 生成回复"""
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }
        
        data = {
            "model": self.model,
            "input": {
                "messages": messages["messages"]
            },
            "parameters": {
                "result_format": "text"
            }
        }
        
        try:
            print(f"[DEBUG] 发送LLM请求: URL={self.api_url}, 消息={data}")
            async with aiohttp.ClientSession() as session:
                async with session.post(self.api_url, json=data, headers=headers) as response:
                    response_text = await response.text()
                    print(f"[DEBUG] LLM响应: HTTP {response.status}, {response_text}")
                    
                    if response.status == 200:
                        result = await response.json()
                        return result["output"]["text"]
                    else:
                        error = f"LLM请求失败: HTTP {response.status} - {response_text}"
                        print(f"[ERROR] {error}")
                        return error
        except Exception as e:
            error = f"LLM请求异常: {str(e)}"
            print(f"[ERROR] {error}")
            traceback.print_exc()
            return error

    async def stream_response(self, messages):
        """流式生成大模型回复"""
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
            "X-DashScope-SSE": "enable"
        }
        
        data = {
            "model": self.model,
            "input": {
                "messages": messages["messages"]
            },
            "parameters": {
                "result_format": "text",
                "stream": True,
                "incremental_output": True
            }
        }

        try:
            print(f"[DEBUG] 发送流式LLM请求: URL={self.api_url}")
            async with aiohttp.ClientSession() as session:
                async with session.post(self.api_url, json=data, headers=headers) as response:
                    async for line in response.content:
                        if not line:
                            continue
                        try:
                            # 解析SSE格式
                            if line.startswith(b'data:'):
                                chunk = line[5:].strip()
                                if chunk:
                                    chunk_data = json.loads(chunk.decode('utf-8'))
                                    if "output" in chunk_data and "text" in chunk_data["output"]:
                                        yield chunk_data["output"]["text"]
                        except Exception as e:
                            print(f"[WARNING] 流式LLM解析异常: {str(e)}")
        except Exception as e:
            print(f"[ERROR] 流式LLM请求失败: {str(e)}")
            traceback.print_exc()

class TTSProvider:
    def __init__(self, config):
        self.access_key_id = config.get('access_key_id')
        self.access_key_secret = config.get('access_key_secret')
        self.appkey = config.get('appkey')
        self.token_url = "https://nls-meta.cn-shanghai.aliyuncs.com"
        self.tts_url = "https://nls-gateway.cn-shanghai.aliyuncs.com/stream/v1/tts"
        self.region_id = "cn-shanghai"
        self.product = "nls-cloud-meta"
        self.voice = config.get('voice', 'xiaoyun')
        self.token = None
        self.token_expire = 0

    async def get_tts_token(self):
        """获取并缓存TTS Token"""
        if self.token and time.time() < self.token_expire:
            return self.token
            
        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        nonce = str(uuid.uuid4())
        
        params = {
            "AccessKeyId": self.access_key_id,
            "Action": "CreateToken",
            "Product": self.product,
            "RegionId": self.region_id,
            "Format": "JSON",
            "SignatureMethod": "HMAC-SHA1",
            "SignatureVersion": "1.0",
            "SignatureNonce": nonce,
            "Timestamp": timestamp,
            "Version": "2019-02-28"
        }
        
        sorted_params = sorted(params.items())
        canonicalized_query_string = "&".join(
            [f"{parse.quote(k, safe='')}={parse.quote(v, safe='')}" for k, v in sorted_params]
        )
        
        string_to_sign = "GET&%2F&" + parse.quote(canonicalized_query_string, safe="")
        
        key = self.access_key_secret + "&"
        h = hmac.new(key.encode('utf-8'), string_to_sign.encode('utf-8'), hashlib.sha1)
        signature = base64.b64encode(h.digest()).decode('utf-8')
        
        params["Signature"] = signature
        
        try:
            print(f"[DEBUG] 获取TTS Token: URL={self.token_url}, params={params}")
            async with aiohttp.ClientSession() as session:
                async with session.get(self.token_url, params=params) as response:
                    if response.status == 200:
                        result = await response.json()
                        self.token = result["Token"]["Id"]
                        self.token_expire = time.time() + 1800 - 60  # 提前60秒刷新
                        print(f"[DEBUG] 获取TTS Token成功: {self.token}")
                        return self.token
                    else:
                        response_text = await response.text()
                        print(f"[ERROR] 获取TTS Token失败: HTTP {response.status} - {response_text}")
        except Exception as e:
            print(f"[ERROR] 获取TTS Token异常: {str(e)}")
            traceback.print_exc()
        return None

    async def text_to_speech(self, text, session_id):
        """同步TTS语音合成"""
        token = await self.get_tts_token()
        if not token:
            print("[ERROR] 无法获取有效的TTS Token")
            return b""
        
        url = f"{self.tts_url}"
        headers = {"Content-Type": "application/json"}
        payload = {
            "appkey": self.appkey,
            "token": token,
            "text": text,
            "format": "wav",
            "voice": self.voice,
            "session_id": session_id
        }
        
        try:
            print(f"[DEBUG] 发送TTS请求: URL={url}, 文本长度={len(text)}")
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=payload, headers=headers) as response:
                    if response.status == 200:
                        audio_data = await response.read()
                        print(f"[DEBUG] TTS合成成功, 音频长度: {len(audio_data)}字节")
                        return audio_data
                    else:
                        error_text = await response.text()
                        error_msg = f"TTS请求失败: HTTP {response.status} - {error_text}"
                        print(f"[ERROR] {error_msg}")
                        return b""
        except Exception as e:
            error_msg = f"TTS请求异常: {str(e)}"
            print(f"[ERROR] {error_msg}")
            traceback.print_exc()
            return b""

    async def stream_speech(self, text, session_id):
        """流式TTS语音合成"""
        token = await self.get_tts_token()
        if not token:
            print("[ERROR] 无法获取有效的TTS Token")
            return
            
        # 阿里云流式TTS参数
        url = f"{self.tts_url}?enable_subtitle=true"  # 启用流式输出
        headers = {"Content-Type": "application/json"}
        payload = {
            "appkey": self.appkey,
            "token": token,
            "text": text,
            "format": "pcm",  # 流式输出使用pcm格式
            "sample_rate": 16000,
            "voice": self.voice,
            "session_id": session_id,
            "stream": True  # 启用流式模式
        }
        
        try:
            print(f"[DEBUG] 发送流式TTS请求: URL={url}, 文本长度={len(text)}")
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=payload, headers=headers) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        print(f"[ERROR] 流式TTS请求失败: HTTP {response.status} - {error_text}")
                        return
                    
                    # 流式接收音频数据
                    async for chunk in response.content.iter_any():
                        if chunk:
                            yield chunk
        except Exception as e:
            print(f"[ERROR] 流式TTS请求异常: {str(e)}")
            traceback.print_exc()

class AliyunProcessor:
    def __init__(self, config):
        self.asr = ASRProvider(config.get('asr', {}))
        self.llm = AliBLProvider(config.get('llm', {}))
        
        tts_config = config.get('tts', {})
        tts_config['access_key_id'] = config.get('asr', {}).get('access_key_id', '')
        tts_config['access_key_secret'] = config.get('asr', {}).get('access_key_secret', '')
        self.tts = TTSProvider(tts_config)

    async def process(self, audio_data):
        try:
            session_id = f"session_{uuid.uuid4().hex[:8]}"
            print(f"[INFO] 开始处理流程, Session ID: {session_id}")
            
            # 1. 语音识别
            print("[DEBUG] 开始ASR识别...")
            text, error = await self.asr.speech_to_text(audio_data, session_id)
            if error or not text:
                error_msg = f"ASR失败: {error}" if error else "ASR返回空结果"
                print(f"[ERROR] {error_msg}")
                return {"error": error_msg}

            # 2. 大模型处理
            print(f"[DEBUG] 调用大模型, 输入文本: '{text}'")
            response = await self.llm.generate_response({
                "messages": [{"role": "user", "content": text}]
            })
            
            if "失败" in response or "错误" in response:
                error_msg = f"LLM处理失败: {response}"
                print(f"[ERROR] {error_msg}")
                return {"error": error_msg}

            # 3. 语音合成
            print(f"[DEBUG] 开始TTS合成, 文本: '{response[:50]}...'")
            tts_audio = await self.tts.text_to_speech(response, session_id)
            if not tts_audio:
                error_msg = "TTS合成失败，返回空音频"
                print(f"[ERROR] {error_msg}")
                return {"error": error_msg}

            print("[INFO] 处理流程完成")
            return {
                "text": text,
                "response": response,
                "audio": tts_audio
            }
        except Exception as e:
            error_msg = f"处理流程异常: {str(e)}"
            print(f"[ERROR] {error_msg}")
            traceback.print_exc()
            return {"error": error_msg}

def create_test_audio(duration=3, sample_rate=16000):
    """生成带语音特征的测试音频"""
    with io.BytesIO() as wav_io:
        with wave.open(wav_io, 'wb') as wav_file:
            wav_file.setnchannels(1)
            wav_file.setsampwidth(2)
            wav_file.setframerate(sample_rate)
            
            frames = b''
            amplitude = 32767 * 0.3
            for i in range(int(sample_rate * duration)):
                base_freq = 250
                formant_freq = 1000
                t = i / sample_rate
                dynamic_freq = base_freq + 50 * math.sin(2 * math.pi * 5 * t)
                
                sample_val = amplitude * (
                    0.5 * (math.sin(2 * math.pi * dynamic_freq * t) + 0.5 * math.sin(4 * math.pi * dynamic_freq * t)) +
                    0.3 * math.sin(2 * math.pi * formant_freq * t) +
                    0.03 * random.uniform(-1, 1))
                
                sample_val = max(-32768, min(32767, sample_val))
                sample = int(sample_val)
                frames += struct.pack('<h', sample)
                
            wav_file.writeframes(frames)
        return wav_io.getvalue()

def convert_audio(audio_data, target_sample_rate=16000, target_channels=1, target_bits=16):
    """使用ffmpeg进行音频格式转换（简化版）"""
    try:
        import subprocess
        import tempfile
        
        with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as inf:
            inf.write(audio_data)
            input_path = inf.name
        output_path = tempfile.mktemp(suffix='.wav')
        
        
        cmd = [
            'ffmpeg', '-y', '-i', input_path,
            '-ar', str(target_sample_rate),
            '-ac', str(target_channels),
            '-acodec', 'pcm_s16le',
            output_path
        ]
        
        subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        
        with open(output_path, 'rb') as f:
            return f.read()
        
    except Exception as e:
        print(f"[WARNING] 音频转换失败: {str(e)}")
        return audio_data
    
SAMPLE_CONFIG = {
    "asr": {
        "sample_rate": 16000,
        "channels": 1,
        "bits": 16,
        "access_key_id": "your_access_key_id",
        "access_key_secret": "your_ceesee_key_sercet",
        "appkey": "your_appkey"
    },
    "tts": {
        "appkey": "your_appkey",
        "voice": "xiaoyun"
    },
    "llm": {
        "access_key_id": "your_access_key_id",
        "access_key_secret": "your_ceesee_key_sercet",
        "api_key": "=your_api_key",
        "model": "qwen-turbo"
    }
}

if __name__ == "__main__":
    # 运行标准处理
    async def main():
        processor = AliyunProcessor(SAMPLE_CONFIG)
        test_audio = create_test_audio()
        result = await processor.process(test_audio)
        
        print("\n=== 处理结果 ===")
        if "error" in result:
            print(f"处理失败: {result['error']}")
        else:
            print(f"识别文本: {result.get('text')}")
            print(f"模型回复: {result.get('response')[:200]}...")
            print(f"音频长度: {len(result.get('audio', b''))} 字节")
    
    asyncio.run(main())