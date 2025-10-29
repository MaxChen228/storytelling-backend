#!/usr/bin/env python3
"""
Gemini API 測試腳本 - 多模式版本
支援 4 種測試模式：單人pro, 單人flash, gemini-pro, gemini-flash
使用方式: python test_api.py [測試模式]
"""

import os
import sys
import wave
from dotenv import load_dotenv
import google.generativeai as genai
from google.cloud import texttospeech


def test_api(model_name="gemini-2.5-flash"):
    """測試 Gemini API 連線"""
    load_dotenv()
    api_key = os.getenv('GEMINI_API_KEY')
    
    if not api_key:
        print("❌ 找不到 GEMINI_API_KEY")
        return False
    
    print(f"✅ API Key: {api_key[:10]}...")
    print(f"🤖 使用模型: {model_name}")
    
    try:
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel(model_name)
        
        print("🧪 測試 API 連線...")
        response = model.generate_content("請簡短回覆 OK")
        
        if response.text:
            print(f"✅ API 測試成功！")
            print(f"📝 回應: {response.text.strip()}")
            return True
        else:
            print("❌ API 回應為空")
            return False
            
    except Exception as e:
        print(f"❌ API 測試失敗: {e}")
        return False


def test_tts_single(model_name="gemini-2.5-flash-tts", voice_name=None, language_code="en-US"):
    """測試單一說話者 TTS"""
    try:
        load_dotenv()
        print(f"🎤 測試單人 TTS...")
        print(f"   模型: {model_name}")
        if voice_name:
            print(f"   聲線: {voice_name}")
        else:
            print("   聲線: 使用服務預設")
        
        client = texttospeech.TextToSpeechClient()
        test_text = "Hello! This is a single speaker TTS test. Testing voice quality and clarity."

        voice_kwargs = {
            "language_code": language_code,
            "model_name": model_name,
        }
        if voice_name:
            voice_kwargs["name"] = voice_name

        response = client.synthesize_speech(
            request=texttospeech.SynthesizeSpeechRequest(
                input=texttospeech.SynthesisInput(text=test_text),
                voice=texttospeech.VoiceSelectionParams(**voice_kwargs),
                audio_config=texttospeech.AudioConfig(
                    audio_encoding=texttospeech.AudioEncoding.LINEAR16,
                    sample_rate_hertz=24000,
                ),
            )
        )
        
        audio_data = response.audio_content
        
        # 根據模型名稱保存不同檔案
        model_suffix = "pro" if "pro" in model_name else "flash"
        filename = f"test_single_{model_suffix}.wav"
        
        with wave.open(filename, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(24000)
            wf.writeframes(audio_data)
        
        print(f"✅ 單人 TTS 測試成功！")
        print(f"🎵 音頻已保存: {filename} ({len(audio_data)/1024:.1f} KB)")
        return True
        
    except Exception as e:
        print(f"❌ 單人 TTS 測試失敗: {e}")
        return False


def main():
    """主程式"""
    # 測試模式對應表
    test_modes = {
        "單人pro": lambda: test_tts_single("gemini-2.5-pro-tts"),
        "單人flash": lambda: test_tts_single("gemini-2.5-flash-tts"),
        "gemini-pro": lambda: test_api("gemini-2.5-pro"),
        "gemini-flash": lambda: test_api("gemini-2.5-flash")
    }
    
    # 取得測試模式
    if len(sys.argv) > 1:
        mode = sys.argv[1]
        
        if mode in test_modes:
            print("=" * 50)
            print(f"執行測試: {mode}")
            print("=" * 50)
            
            success = test_modes[mode]()
            
            print("=" * 50)
            if success:
                print(f"🎉 {mode} 測試通過！")
            else:
                print(f"💥 {mode} 測試失敗！")
                sys.exit(1)
        else:
            print(f"❌ 未知的測試模式: {mode}")
            print(f"可用模式: {', '.join(test_modes.keys())}")
            sys.exit(1)
    else:
        # 沒有參數時顯示使用說明
        print("=" * 50)
        print("Gemini API 測試工具")
        print("=" * 50)
        print("\n使用方式: python test_api.py [測試模式]\n")
        print("可用的測試模式:")
        print("  單人pro    - 單一說話者 TTS (pro 模型)")
        print("  單人flash  - 單一說話者 TTS (flash 模型)")
        print("  gemini-pro   - 基本 API 測試 (pro 模型)")
        print("  gemini-flash - 基本 API 測試 (flash 模型)")
        print("\n範例:")
        print("  python test_api.py 單人pro")
        print("  python test_api.py gemini-flash")
        print("=" * 50)


if __name__ == "__main__":
    main()
