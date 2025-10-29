#!/usr/bin/env python3
"""
Gemini API 測試腳本 - 多模式版本
支援 6 種測試模式：對談pro, 對談flash, 單人pro, 單人flash, gemini-pro, gemini-flash
使用方式: python test_api.py [測試模式]
"""

import os
import sys
import wave
from dotenv import load_dotenv
import google.generativeai as genai
from google import genai as new_genai
from google.genai import types


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


def test_tts_single(model_name="gemini-2.5-flash-preview-tts", voice_name="Kore"):
    """測試單一說話者 TTS"""
    load_dotenv()
    api_key = os.getenv('GEMINI_API_KEY')
    
    if not api_key:
        print("❌ 找不到 GEMINI_API_KEY")
        return False
    
    try:
        print(f"🎤 測試單人 TTS...")
        print(f"   模型: {model_name}")
        print(f"   聲線: {voice_name}")
        
        client = new_genai.Client(api_key=api_key)
        test_text = "Hello! This is a single speaker TTS test. Testing voice quality and clarity."
        
        response = client.models.generate_content(
            model=model_name,
            contents=test_text,
            config=types.GenerateContentConfig(
                response_modalities=["AUDIO"],
                speech_config=types.SpeechConfig(
                    voice_config=types.VoiceConfig(
                        prebuilt_voice_config=types.PrebuiltVoiceConfig(
                            voice_name=voice_name
                        )
                    )
                )
            )
        )
        
        audio_data = response.candidates[0].content.parts[0].inline_data.data
        
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


def test_tts_multi(model_name="gemini-2.5-flash-preview-tts"):
    """測試多說話者對話 TTS"""
    load_dotenv()
    api_key = os.getenv('GEMINI_API_KEY')
    
    if not api_key:
        print("❌ 找不到 GEMINI_API_KEY")
        return False
    
    try:
        print(f"🎭 測試對談 TTS (Multi-Speaker)...")
        print(f"   模型: {model_name}")
        print(f"   主持人: Kore")
        print(f"   專家: Puck")
        
        client = new_genai.Client(api_key=api_key)
        
        # 簡短對話腳本
        conversation = """Person1: Welcome to our tech podcast! Today we're discussing AI.
Person2: Thanks for having me! AI is truly transforming our world.
Person1: What's the most exciting development you've seen recently?
Person2: I'd say the advances in language models are remarkable."""
        
        response = client.models.generate_content(
            model=model_name,
            contents=conversation,
            config=types.GenerateContentConfig(
                response_modalities=["AUDIO"],
                speech_config=types.SpeechConfig(
                    multi_speaker_voice_config=types.MultiSpeakerVoiceConfig(
                        speaker_voice_configs=[
                            types.SpeakerVoiceConfig(
                                speaker="Person1",
                                voice_config=types.VoiceConfig(
                                    prebuilt_voice_config=types.PrebuiltVoiceConfig(
                                        voice_name="Kore"
                                    )
                                )
                            ),
                            types.SpeakerVoiceConfig(
                                speaker="Person2",
                                voice_config=types.VoiceConfig(
                                    prebuilt_voice_config=types.PrebuiltVoiceConfig(
                                        voice_name="Puck"
                                    )
                                )
                            )
                        ]
                    )
                )
            )
        )
        
        audio_data = response.candidates[0].content.parts[0].inline_data.data
        
        # 根據模型名稱保存不同檔案
        model_suffix = "pro" if "pro" in model_name else "flash"
        filename = f"test_multi_speaker_{model_suffix}.wav"
        
        with wave.open(filename, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(24000)
            wf.writeframes(audio_data)
        
        print(f"✅ 對談 TTS 測試成功！")
        print(f"🎵 音頻已保存: {filename} ({len(audio_data)/1024:.1f} KB)")
        return True
        
    except Exception as e:
        print(f"❌ 對談 TTS 測試失敗: {e}")
        if "MultiSpeakerVoiceConfig" in str(e):
            print("💡 提示: 請確認 google-genai >= 1.31.0")
        return False


def main():
    """主程式"""
    # 測試模式對應表
    test_modes = {
        "對談pro": lambda: test_tts_multi("gemini-2.5-pro-preview-tts"),
        "對談flash": lambda: test_tts_multi("gemini-2.5-flash-preview-tts"),
        "單人pro": lambda: test_tts_single("gemini-2.5-pro-preview-tts"),
        "單人flash": lambda: test_tts_single("gemini-2.5-flash-preview-tts"),
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
        print("  對談pro    - Multi-Speaker TTS (pro 模型)")
        print("  對談flash  - Multi-Speaker TTS (flash 模型)")
        print("  單人pro    - 單一說話者 TTS (pro 模型)")
        print("  單人flash  - 單一說話者 TTS (flash 模型)")
        print("  gemini-pro   - 基本 API 測試 (pro 模型)")
        print("  gemini-flash - 基本 API 測試 (flash 模型)")
        print("\n範例:")
        print("  python test_api.py 對談pro")
        print("  python test_api.py gemini-flash")
        print("=" * 50)


if __name__ == "__main__":
    main()