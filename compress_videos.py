"""
Скрипт для сжатия видео с помощью ffmpeg.
Уменьшает размер файлов при сохранении приемлемого качества.

Использование:
    python compress_videos.py
    
Требования:
    - ffmpeg должен быть установлен и доступен в PATH
"""

import subprocess
import shutil
from pathlib import Path

# Путь к ffmpeg (если не в PATH)
FFMPEG_PATH = r"E:\ffmpeg-bin\ffmpeg-8.0.1-essentials_build\bin\ffmpeg.exe"

VIDEOS_DIR = Path(__file__).parent / "video"
BACKUP_DIR = Path(__file__).parent / "video_backup"
COMPRESSED_SUFFIX = "_compressed"

# Настройки сжатия
CRF = 28  # Качество: 18-23 = высокое, 24-28 = среднее, 29-35 = низкое
PRESET = "fast"  # ultrafast, superfast, veryfast, faster, fast, medium, slow
AUDIO_BITRATE = "96k"  # Битрейт аудио


def check_ffmpeg() -> bool:
    """Проверяет, установлен ли ffmpeg."""
    try:
        subprocess.run(
            [FFMPEG_PATH, "-version"],
            capture_output=True,
            check=True
        )
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False


def compress_video(input_path: Path, output_path: Path) -> bool:
    """Сжимает видео с помощью ffmpeg."""
    cmd = [
        FFMPEG_PATH,
        "-i", str(input_path),
        "-c:v", "libx264",
        "-crf", str(CRF),
        "-preset", PRESET,
        "-c:a", "aac",
        "-b:a", AUDIO_BITRATE,
        "-movflags", "+faststart",  # Оптимизация для стриминга
        "-y",  # Перезаписать без вопросов
        str(output_path)
    ]
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True)
        return result.returncode == 0
    except Exception as e:
        print(f"  Error: {e}")
        return False


def get_file_size_mb(path: Path) -> float:
    """Возвращает размер файла в мегабайтах."""
    return path.stat().st_size / (1024 * 1024)


def main():
    if not check_ffmpeg():
        print("[X] ffmpeg not found! Install ffmpeg and add to PATH.")
        print("    Download: https://ffmpeg.org/download.html")
        return
    
    if not VIDEOS_DIR.exists():
        print(f"[X] Folder {VIDEOS_DIR} not found!")
        return
    
    # Создаём папку для резервных копий
    BACKUP_DIR.mkdir(exist_ok=True)
    
    videos = list(VIDEOS_DIR.glob("*.mp4"))
    if not videos:
        print("No videos found for compression.")
        return
    
    print(f"[*] Found {len(videos)} videos to compress\n")
    
    total_before = 0
    total_after = 0
    
    for video_path in videos:
        original_size = get_file_size_mb(video_path)
        total_before += original_size
        
        print(f"[>] {video_path.name} ({original_size:.2f} MB)")
        
        # Временный файл для сжатого видео
        temp_output = video_path.with_suffix(".tmp.mp4")
        
        if compress_video(video_path, temp_output):
            new_size = get_file_size_mb(temp_output)
            
            # Проверяем, есть ли смысл в сжатии (уменьшилось хотя бы на 10%)
            if new_size < original_size * 0.9:
                # Сохраняем оригинал в backup
                backup_path = BACKUP_DIR / video_path.name
                shutil.copy2(video_path, backup_path)
                
                # Заменяем оригинал сжатым
                temp_output.replace(video_path)
                
                savings = original_size - new_size
                percent = (savings / original_size) * 100
                print(f"   [OK] {original_size:.2f} -> {new_size:.2f} MB (saved {savings:.2f} MB, {percent:.1f}%)")
                total_after += new_size
            else:
                print(f"   [SKIP] Compression not effective")
                temp_output.unlink()
                total_after += original_size
        else:
            print(f"   [X] Compression error")
            if temp_output.exists():
                temp_output.unlink()
            total_after += original_size
    
    print(f"\n[=] Total: {total_before:.2f} -> {total_after:.2f} MB")
    print(f"    Saved: {total_before - total_after:.2f} MB ({((total_before - total_after) / total_before) * 100:.1f}%)")
    print(f"\n[i] Originals saved in: {BACKUP_DIR}")


if __name__ == "__main__":
    main()
