#!/usr/bin/env python3

import os
import glob
import argparse
from pydub import AudioSegment
import speech_recognition as sr
from googletrans import Translator, LANGUAGES
import openai
import time
import glob
import re

# API Keys - ensure to fill these with your actual API keys where needed
OPENAI_API_KEY = None
GOOGLE_CLOUD_SPEECH_API_KEY = None
WIT_AI_API_KEY = None
AZURE_SPEECH_API_KEY =  None
HOUNDIFY_CLIENT_ID =  None
HOUNDIFY_CLIENT_KEY =  None
IBM_SPEECH_TO_TEXT_API_KEY =  None
IBM_SERVICE_URL =  None

# Global Settings
RETRY_DELAY = 3  
RETRY_COUNT = 3
translator = Translator(service_urls=['translate.googleapis.com'])
r = sr.Recognizer()
openai.api_key = OPENAI_API_KEY

def atoi(text):
    return int(text) if text.isdigit() else text

def natural_keys(text):
    return [ atoi(c) for c in re.split(r'(\d+)', text) ]

def get_audio_files(folder_path):
    """Return a list of audio file paths from the given folder, sorted in human-readable ascending order."""
    files_grabbed = []
    for files in ('*.mp3', '*.wav'):  # Extend or adjust as needed
        files_grabbed.extend(glob.glob(os.path.join(folder_path, files)))
    
    # Sort the files using the natural_keys function
    files_grabbed.sort(key=natural_keys)
    
    return files_grabbed

def transcribe_with_whisper(audio_path, rec_language='en'):
    """Transcribe audio using OpenAI's Whisper model."""
    try:
        with open(audio_path, "rb") as audio_file:
            transcript = openai.Audio.transcribe('whisper-1', audio_file)
            if 'text' in transcript:
                return {"service": "Whisper", "text": transcript['text']}
            else:
                return {"service": "Whisper", "error": "Transcription failed without specific error message."}
    except Exception as e:
        return {"service": "Whisper", "error": str(e)}

def transcribe_audio(file_path, rec_language):
    """Transcribe audio using various services."""
    # Convert to WAV if needed for compatibility
    audio, wav_path = convert_to_wav(file_path)

    results = {}
    with sr.AudioFile(wav_path) as source:
        audio_data = r.record(source)

              # Check and use Google Cloud Speech API
        if GOOGLE_CLOUD_SPEECH_API_KEY:
            try:
                text = r.recognize_google_cloud(audio_data, credentials_json=GOOGLE_CLOUD_SPEECH_API_KEY, language=rec_language)
                results['GOOGLE'] = text
                print('[+] Transcribed using', 'GOOGLE CLOUD API')
            except sr.UnknownValueError:
                error = "Google Cloud Speech could not understand audio"
            except sr.RequestError as e:
                error = f"Could not request results from Google Cloud Speech service; {e}"

        # Check and use Wit.ai
        if WIT_AI_API_KEY:
            try:
                text = r.recognize_wit(audio_data, key=WIT_AI_API_KEY)
                results['WIT'] = text
                print('[+] Transcribed using', 'WIT API')
            except sr.UnknownValueError:
                error = "Wit.ai could not understand audio"
            except sr.RequestError as e:
                error = f"Could not request results from Wit.ai service; {e}"

        # Check and use Azure Speech
        if AZURE_SPEECH_API_KEY:
            try:
                text = r.recognize_azure(audio_data, key=AZURE_SPEECH_API_KEY, language=rec_language)
                results['AZURE'] = text
                print('[+] Transcribed using', 'AZURE SPEECH API')
            except sr.UnknownValueError:
                error = "Azure Speech could not understand audio"
            except sr.RequestError as e:
                error = f"Could not request results from Azure Speech service; {e}"

        # Check and use Houndify
        if HOUNDIFY_CLIENT_ID and HOUNDIFY_CLIENT_KEY:
            try:
                text = r.recognize_houndify(audio_data, client_id=HOUNDIFY_CLIENT_ID, client_key=HOUNDIFY_CLIENT_KEY)
                results['HOUNDIFY'] = text
                print('[+] Transcribed using', 'WIT API')
            except sr.UnknownValueError:
                error = "Houndify could not understand audio"
            except sr.RequestError as e:
                error = f"Could not request results from Houndify service; {e}"

        # Check and use IBM Speech to Text
        if IBM_SPEECH_TO_TEXT_API_KEY and IBM_SERVICE_URL:
            try:
                r.recognizer_instance().set_service_url(IBM_SERVICE_URL)  # Set the service URL for the IBM instance
                text = r.recognize_ibm(audio_data, username="apikey", password=IBM_SPEECH_TO_TEXT_API_KEY, language=rec_language)
                results['IBM'] = text
                print('[+] Transcribed using', 'IBM SPEECH TO TEXT')
            except sr.UnknownValueError:
                error = "IBM Speech to Text could not understand audio"
            except sr.RequestError as e:
                error = f"Could not request results from IBM Speech to Text service; {e}"

        # Whisper
        if OPENAI_API_KEY:
            try:
                text = transcribe_with_whisper(wav_path, rec_language)
                results['WHISPER'] = text
                print('[+] Transcribed using', 'WHISPER')
            except sr.UnknownValueError:
                error = "OpenAI Whisper could not understand audio"
            except sr.RequestError as e:
                error = f"Could not request results from OpenAI Whisper service; {e}"

    return results

def convert_to_wav(file_path):
    """Convert audio file to WAV format if necessary."""
    wav_path = file_path.rsplit('.', 1)[0] + ".wav"  # Define wav_path outside the if-else
    if not file_path.endswith('.wav'):
        audio = AudioSegment.from_file(file_path)
        audio.export(wav_path, format="wav")
        return audio, wav_path  # Return audio and wav_path after conversion
    else:
        return None, wav_path  # Return None for audio when no conversion is done

def translate_text(text, target_language):
    """Translate text using Google Translate with retries."""
    for attempt in range(RETRY_COUNT):
        try:
            translated_text = translator.translate(text, lang_tgt=target_language).text
            if translated_text:
                return translated_text
            else:
                raise Exception("Translation returned an empty response.")
        except Exception as e:
            print(f"Attempt {attempt + 1}: Translation error - {e}")
            if attempt < RETRY_COUNT - 1:
                time.sleep(RETRY_DELAY)
    return "Translation failed after all attempts."

def process_files(folder_path, rec_language, trans_language=None):
    """Process audio files for transcription and optional translation."""
    files = get_audio_files(folder_path)
    aggregated_results = {}

    # Process each file and aggregate results by service
    for file in files:
        if not file.endswith('.wav'):
            continue

        print()
        print(f"[***] Processing file: {os.path.basename(file)}")
        file_results = transcribe_audio(file, rec_language)
        
        for service, result in file_results.items():
            if service not in aggregated_results:
                aggregated_results[service] = []
            # Append text result or the entire result for later processing
            if isinstance(result, dict) and "text" in result:
                aggregated_results[service].append(result['text'])
            elif isinstance(result, str):
                aggregated_results[service].append(result)
            else:
                aggregated_results[service].append(result.get('error', 'Unknown error'))

    # Process aggregated results for each service
    for service, texts in aggregated_results.items():
        combined_text = "\n".join(texts)
        print(f"[+] Results from {service}:\n{combined_text}")
        
        # Perform and print translation if requested
        if trans_language and combined_text.strip():
            translated_text = translate_text(combined_text, trans_language)
            print()
            print(f"[+] Translation of {service} transcription to {trans_language}:\n{translated_text}")

def main():
    parser = argparse.ArgumentParser(description="Transcribe audio files and optionally translate the output.")
    parser.add_argument("folder_path", type=str, help="Folder containing audio files.")
    parser.add_argument("-l", "--rec_language", type=str, choices=list(LANGUAGES.keys()), help="Recognition language.")
    parser.add_argument("-t", "--translate", type=str, choices=list(LANGUAGES.keys()), help="Target language for translation.", default=None)
    args = parser.parse_args()

    process_files(args.folder_path, args.rec_language, args.translate)

if __name__ == "__main__":
    main()
