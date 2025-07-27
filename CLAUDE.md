# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a two-stage Streamlit application for voice-based address extraction using Azure Speech Services. The app uses a structured workflow: first capturing postal codes via voice input, then detailed address information, with confirmation steps between each stage.

## Development Commands

```bash
# Install dependencies
pip install -r requirements.txt

# Run the Streamlit app
streamlit run app.py
```

## Architecture

The application consists of four main modules:

- `app.py` - Main Streamlit UI with three-step workflow (postal code → detail address → completion)
- `speech_service.py` - Azure Speech Services integration for STT and TTS functionality  
- `address_extractor.py` - Pattern recognition for postal codes and Japanese address details
- `postal_code_service.py` - Integration with zipcloud API for postal code to address conversion

## Configuration

Environment variables (create `.env` from `.env.example`):
- `AZURE_SPEECH_KEY` - Azure Speech Services API key
- `AZURE_SPEECH_REGION` - Azure region (e.g., "japaneast")
- `AUDIO_SAMPLE_RATE` - Audio recording sample rate (default: 16000)
- `AUDIO_CHANNELS` - Audio channels (default: 1)