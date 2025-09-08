#!/usr/bin/env python3
"""
Download script for ggml-base.en.bin model file.
Downloads the Whisper base model and saves it to the models/ directory.
"""

import os
import sys
import requests
from pathlib import Path
from tqdm import tqdm

def download_file(url, destination):
    """Download a file with progress bar."""
    response = requests.get(url, stream=True)
    response.raise_for_status()
    
    total_size = int(response.headers.get('content-length', 0))
    
    with open(destination, 'wb') as file, tqdm(
        desc=os.path.basename(destination),
        total=total_size,
        unit='B',
        unit_scale=True,
        unit_divisor=1024,
    ) as progress_bar:
        for chunk in response.iter_content(chunk_size=8192):
            size = file.write(chunk)
            progress_bar.update(size)

def main():
    # Model URL (using the official Hugging Face model)
    model_url = "https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-base.en.bin"
    
    # Ensure models directory exists
    models_dir = Path(__file__).parent / "models"
    models_dir.mkdir(exist_ok=True)
    
    # Destination file path
    model_path = models_dir / "ggml-base.en.bin"
    
    # Check if model already exists
    if model_path.exists():
        print(f"Model already exists at {model_path}")
        print(f"File size: {model_path.stat().st_size / (1024*1024):.1f} MB")
        response = input("Do you want to re-download? (y/N): ").strip().lower()
        if response != 'y':
            print("Skipping download.")
            return
    
    print(f"Downloading ggml-base.en.bin to {model_path}")
    print(f"URL: {model_url}")
    
    try:
        download_file(model_url, model_path)
        print(f"\n✅ Successfully downloaded model to {model_path}")
        print(f"File size: {model_path.stat().st_size / (1024*1024):.1f} MB")
    except requests.exceptions.RequestException as e:
        print(f"❌ Error downloading model: {e}")
        sys.exit(1)
    except KeyboardInterrupt:
        print("\n❌ Download cancelled by user")
        if model_path.exists():
            model_path.unlink()
        sys.exit(1)

if __name__ == "__main__":
    main()
