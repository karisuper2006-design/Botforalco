"""
Скрипт для сжатия видео коктейлей.
Требует установленного FFmpeg: https://ffmpeg.org/download.html

Использование:
    python compress_videos.py

Скрипт сожмёт все видео больше 3 МБ и создаст резервные копии оригиналов.
"""

import subprocess
import shutil
import sys
from pathlib import Path

# Исправляем кодировку для Windows
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

# Настройки
VIDEO_DIR = Path(__file__).parent / "video"
BACKUP_DIR = Path(__file__).parent / "video_backup"
MAX_SIZE_MB = 3  # Сжимать файлы больше этого размера
TARGET_WIDTH = 720  # Целевая ширина видео
CRF = 28  # Качество (18-28, чем выше - меньше размер, ниже качество)


def get_file_size_mb(path: Path) -> float:
    """Возвращает размер файла в мегабайтах."""
    return path.stat().st_size / (1024 * 1024)


def compress_video(input_path: Path, output_path: Path) -> bool:
    """Сжимает видео с помощью FFmpeg."""
    cmd = [
        "ffmpeg",
        "-i", str(input_path),
        "-vcodec", "libx264",
        "-crf", str(CRF),
        "-preset", "fast",
        "-vf", f"scale={TARGET_WIDTH}:-2",
        "-acodec", "aac",
        "-b:a", "128k",
        "-y",  # Перезаписывать без вопросов
        str(output_path)
    ]
    
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=True
        )
        return True
    except subprocess.CalledProcessError as e:
        print(f"  [ERROR] {e.stderr}")
        return False
    except FileNotFoundError:
        print("  [ERROR] FFmpeg не найден! Установите его: https://ffmpeg.org/download.html")
        return False


def main():
    if not VIDEO_DIR.exists():
        print(f"[ERROR] Папка {VIDEO_DIR} не найдена!")
        return

    # Создаём папку для резервных копий
    BACKUP_DIR.mkdir(exist_ok=True)
    
    videos = list(VIDEO_DIR.glob("*.mp4"))
    print(f"[INFO] Найдено {len(videos)} видео в {VIDEO_DIR}\n")
    
    compressed_count = 0
    skipped_count = 0
    
    for video_path in sorted(videos):
        size_mb = get_file_size_mb(video_path)
        
        if size_mb <= MAX_SIZE_MB:
            print(f"[SKIP] {video_path.name}: {size_mb:.1f} MB - уже маленький")
            skipped_count += 1
            continue
        
        print(f"[COMPRESS] {video_path.name}: {size_mb:.1f} MB - сжимаем...")
        
        # Создаём резервную копию
        backup_path = BACKUP_DIR / video_path.name
        if not backup_path.exists():
            shutil.copy2(video_path, backup_path)
            print(f"  [BACKUP] {backup_path}")
        
        # Временный файл для сжатого видео
        temp_path = video_path.with_suffix(".temp.mp4")
        
        if compress_video(video_path, temp_path):
            new_size_mb = get_file_size_mb(temp_path)
            
            # Заменяем оригинал сжатым
            temp_path.replace(video_path)
            
            reduction = ((size_mb - new_size_mb) / size_mb) * 100
            print(f"  [OK] Сжато: {size_mb:.1f} MB -> {new_size_mb:.1f} MB (-{reduction:.0f}%)")
            compressed_count += 1
        else:
            # Удаляем временный файл при ошибке
            if temp_path.exists():
                temp_path.unlink()
    
    print(f"\n[RESULT]")
    print(f"   Сжато: {compressed_count}")
    print(f"   Пропущено: {skipped_count}")
    print(f"   Резервные копии: {BACKUP_DIR}")


if __name__ == "__main__":
    main()
